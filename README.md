# swisssurface_dtm
Scripts to generate digital terrain model TMS tiles from swissSurface point cloud data

Note: these scripts at the current stage are just a combination of copy pastes from tutorials. There is a lot of things that can be improved on.

## Required tools:

- pdal: https://pdal.io/
- gdal: https://gdal.org/
- ImageMagick: https://imagemagick.org/index.php
- Python


## Step by step:

Note: As there are a lot of data intense intermediate steps it can be advantageous to use a ramdisk to store intermediate results.

1. Export csv file to the swissSURFACE3D data from the Swisstopo homepage: https://www.swisstopo.admin.ch/de/geodata/height/surface3d.html#download (via the "Export all links" button)

2. Download the point cloud data. The 'downloader.py' script can be used for this step.

3. Using the `create_dem.py`ground points can be identified. Using these points first digital terrain model is created. This model is then used to create a hillshade.

4. All hillshade tiles can be converted to a single GeoTiff by first creating a virtual dataset: 

    ```
    gdalbuildvrt hillshade.vrt hillshade/*tif
    ```

    and then converting this virtual dataset into a GeoTiff:

    ```
    gdal_translate -of GTiff -co COMPRESS=LZW -co BIGTIFF=YES hillshade.vrt hillshade.tif
    ```

5. TMS tiles (in PNG) format can then be created with the following command:

    ```
    gdal2tiles.py --processes 16 -z 16-19 -s EPSG:2056 -e hillshade.tif tms
    ```

6. Using `convert_to_jpeg.py` these tiles are then converted to the JPEG format to reduce disk space,
