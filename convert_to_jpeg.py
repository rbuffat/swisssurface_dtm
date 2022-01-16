import glob
import os
import subprocess
import multiprocessing as mp
import pathlib

# Delete empty files to reduce total size, especially when converted to jpeg
i = 0
for fpath in glob.glob(os.path.join(os.path.dirname(os.path.realpath(__file__)), "tms", "**", "*.png"), recursive=True):
    i+= 1
    if i % 100000 == 0:
        print(i)

    size = os.path.getsize(fpath)
    if size == 206:
        # print("delete", fpath, size)
        os.remove(fpath)

# Convert from png to jpeg
def process_directory(dir_path: str) -> None:

    # Create new dir if not yet exist
    new_dir_path = dir_path.replace("tms", "tmsjpeg")
    pathlib.Path(new_dir_path).mkdir(parents=True, exist_ok=True)

    commands = ["magick", "mogrify", "-format", "jpg", "-quality", "80", "-path", new_dir_path, os.path.join(dir_path, "*.png")]
    subprocess.run(
        subprocess.list2cmdline(commands), shell=True, stdout=subprocess.DEVNULL
    )


dir_paths = glob.glob(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "tms", "**", ""),
    recursive=True,
)

with mp.Pool(16) as p:
    p.map(process_directory, dir_paths)
