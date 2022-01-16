import glob
import json
import multiprocessing as mp
import os
import subprocess
import zipfile

tiles_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "tiles")

RAMDISK_PATH = "/tmp/ramdisk"


def create_ground(tile_path: str) -> None:

    print(tile_path)

    # Unpack zip to ramdisk
    with zipfile.ZipFile(tile_path, "r") as zip:
        las_name = zip.namelist()[0]

        # Filter groundpoints
        las_path = os.path.join(RAMDISK_PATH, las_name)

        # las_ground_path = las_path.replace(".las", "_ground.laz")
        las_ground_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "ground",
            las_name.replace(".las", "_ground.laz"),
        )
        if not os.path.exists(las_ground_path):

            zip.extractall(RAMDISK_PATH)

            commands = [
                "pdal",
                "translate",
                las_path,
                "-o",
                las_ground_path,
                "outlier",
                "smrf",
                "range",
                "--filters.outlier.method='statistical'",
                "--filters.outlier.mean_k=8",
                "--filters.outlier.multiplier=3.0",
                "--filters.smrf.ignore='Classification[7:7]'",
                "--filters.range.limits='Classification[2:2]'",
                "--writers.las.compression=true",
                "--verbose",
                "0",
            ]
            subprocess.run(subprocess.list2cmdline(commands), shell=True)
            os.remove(las_path)
        else:
            print("skip", tile_path)


def create_dtm(tile_path: str) -> None:

    ground_tiles_path = os.path.dirname(tile_path)

    # Calc tile bounds
    # Lower left corner is encoded in filename
    path_parts = os.path.basename(tile_path).split("_")
    x_str = path_parts[0]
    y_str = path_parts[1]
    x = int(x_str)
    y = int(y_str)
    minx = x * 1000.0
    miny = y * 1000.0
    maxx = minx + 1000.0 - 0.25
    maxy = miny + 1000.0 - 0.25

    dtm_file_name = f"dtm_{x}_{y}.tif"
    dtm_filled_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "dtm", dtm_file_name
    )

    if os.path.exists(dtm_filled_path):
        print("already exists, skipping", dtm_filled_path)
        return

    # Merge sourrounding tiles into one
    merged_path = os.path.join(
        RAMDISK_PATH, os.path.basename(tile_path).replace(".laz", "_merged.laz")
    )
    neighobor_tiles = [tile_path]
    for dx, dy in [
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
        (1, 0),
        (1, -1),
        (0, -1),
    ]:
        neighbor_tile_name = f"{x+dx}_{y+dy}_ground.laz"
        neighbor_tile_path = os.path.join(ground_tiles_path, neighbor_tile_name)
        if os.path.exists(neighbor_tile_path):
            neighobor_tiles.append(neighbor_tile_path)

    commands = ["pdal", "merge"] + neighobor_tiles + [merged_path]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )

    # Crop
    cropped_path = os.path.join(
        RAMDISK_PATH, os.path.basename(tile_path).replace(".laz", "_cropped.laz")
    )
    commands = [
        "pdal",
        "translate",
        merged_path,
        "-o",
        cropped_path,
        "filters.crop",
        f"--filters.crop.bounds=([{minx-50}, {maxx+50}],[{miny-50}, {maxy+50}])",
        "--writers.las.compression=true",
        "--verbose",
        "0",
    ]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )
    os.remove(merged_path)

    # Create DTM
    dtm_path = os.path.join(RAMDISK_PATH, f"dtm_{x}_{y}.tif")
    pipeline_path = os.path.join(RAMDISK_PATH, f"pipeline_{x}_{y}.json")

    pipeline_json = {
        "pipeline": [
            cropped_path,
            {
                "filename": dtm_path,
                "gdaldriver": "GTiff",
                "output_type": "all",
                "resolution": 0.25,
                "type": "writers.gdal",
                "override_srs": "EPSG:2056",
                "bounds": f"([{minx}, {maxx}],[{miny}, {maxy}])",
            },
        ]
    }
    with open(pipeline_path, "w") as f:
        json.dump(pipeline_json, f)

    commands = ["pdal", "pipeline", pipeline_path]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )
    os.remove(cropped_path)
    os.remove(pipeline_path)

    # Fill gaps
    commands = ["gdal_fillnodata.py", "-md", "50", dtm_path, dtm_filled_path]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )
    os.remove(dtm_path)

    # TODO compression?


def create_hillshade(dtm_tile_path: str) -> None:

    dtm_tiles_path = os.path.dirname(dtm_tile_path)

    # Calc tile bounds
    # Lower left corner is encoded in filename
    path_parts = os.path.basename(dtm_tile_path).split(".")[0].split("_")
    x = int(path_parts[1])
    y = int(path_parts[2])
    minx = x * 1000.0
    miny = y * 1000.0
    maxx = minx + 1000.0
    maxy = miny + 1000.0

    hillshade_cropped_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "hillshade",
        f"hillshade_{x}_{y}.tif",
    )
    if os.path.exists(hillshade_cropped_path):
        print("already exists, skipping", hillshade_cropped_path)
        return

    neighobor_tiles = [dtm_tile_path]
    for dx, dy in [
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
        (1, 0),
        (1, -1),
        (0, -1),
    ]:
        neighbor_tile_name = f"dtm_{x+dx}_{y+dy}.tif"
        neighbor_tile_path = os.path.join(dtm_tiles_path, neighbor_tile_name)
        if os.path.exists(neighbor_tile_path):
            neighobor_tiles.append(neighbor_tile_path)

    # Create virtual raster
    vrt_path = os.path.join(RAMDISK_PATH, f"{x}_{y}.vrt")
    commands = [
        "gdalbuildvrt",
        vrt_path,
    ] + neighobor_tiles
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )

    # Create dtm
    hillshade_full_path = os.path.join(RAMDISK_PATH, f"hillshade_{x}_{y}.tif")
    commands = [
        "gdaldem",
        "hillshade",
        vrt_path,
        hillshade_full_path,
        "-alg",
        "Horn",
        "-s",
        "1.0",
        "-z",
        "0.5",
        "-alt",
        "42.5",
        "-multidirectional",
    ]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )
    os.remove(vrt_path)

    # Crop
    commands = [
        "gdal_translate",
        "-of",
        "GTiff",
        "-co",
        "COMPRESS=LZW",
        "-projwin",
        str(minx),
        str(maxy),
        str(maxx),
        str(miny),
        hillshade_full_path,
        hillshade_cropped_path,
    ]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )
    os.remove(hillshade_full_path)


# # Remove ground points
files = glob.glob(os.path.join(tiles_path, "*.las.zip"), recursive=True)
with mp.Pool(16) as p:
    p.map(create_ground, files)


def dtm_path_exists(tile_path: str) -> bool:
    # Calc tile bounds
    # Lower left corner is encoded in filename
    path_parts = os.path.basename(tile_path).split("_")
    x_str = path_parts[0]
    y_str = path_parts[1]
    x = int(x_str)
    y = int(y_str)
    dtm_file_name = f"dtm_{x}_{y}.tif"
    dtm_filled_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "dtm", dtm_file_name
    )
    return os.path.exists(dtm_filled_path)


# Create dtm
files = glob.glob(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "ground", "*.laz"),
    recursive=True,
)
files = [f for f in files if not dtm_path_exists(f)]
with mp.Pool(10) as p:
    p.map(create_dtm, files)

# Create hillshade
files = glob.glob(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "dtm", "*.tif"),
    recursive=True,
)
with mp.Pool(16) as p:
    p.map(create_hillshade, files)
