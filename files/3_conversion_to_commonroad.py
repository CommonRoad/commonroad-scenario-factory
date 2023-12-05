import logging
from pathlib import Path
from scenario_factory.globetrotter.globetrotter_io import osm2commonroad

logging.basicConfig(level=logging.INFO)

osm_files = Path("extracted_maps").glob('*.osm')

for osm_file in osm_files:
    logging.info(f"======== Converting {osm_file.stem} ========")
    if osm_file.stem == "DEU_Berlin":  # TODO debug error for Berlin map
        continue
    commonroad_file = osm_file.parent.joinpath("..", "commonroad", f"{osm_file.stem}.xml")
    osm2commonroad(osm_file, commonroad_file)
    print(commonroad_file)