import os
import subprocess


with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ch.swisstopo.swisssurface3d-TrdWouHM.csv")) as f:
    for line in f:
        try:
            url = line.strip()
            download_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "tiles", url.rsplit("/")[-1])
            if os.path.exists(download_path):
                continue
            subprocess.run(["wget", "-q", url, "-P", "tiles"])
        except Exception as e:
            print(e)
