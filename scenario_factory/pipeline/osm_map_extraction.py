import logging
import os
from pathlib import Path

import pandas as pd
from pandas import Series


def extract_osm_maps(cities_file: Path, input_maps_folder: Path, overwrite: bool = False) -> Path:
    """
    Extract the OSM map according to bounding box specified in the cities_file. Calls osmium library.
    # TODO use overpass web API instead? https://wiki.openstreetmap.org/wiki/Overpass_API

    Args:
        cities_file (Path): Path to the cities file.
        input_maps_folder (Path): Path to the folder containing the input OSM map files.
        overwrite (bool): Overwrite existing OSM map extraction files.

    Returns:
        Path: Path to the folder with the extracted OSM maps.
    """
    output_folder = cities_file.parent.joinpath("extracted_maps")
    output_folder.mkdir(parents=True, exist_ok=True)

    with open(cities_file, newline="") as csvfile:
        cities = pd.read_csv(csvfile)

        def bbox_str(entry: Series) -> str:
            return f"{entry['West']},{entry['South']},{entry['East']},{entry['North']}"

        for row, entry in cities.iterrows():
            output_file = output_folder.joinpath(f"{entry['Country']}_{entry['City']}.osm")
            execute_osmium = True
            try:
                match entry["Country"]:
                    case "DEU":
                        if entry["City"] == "Bremen":  # used for example
                            input_file = input_maps_folder.joinpath("bremen-latest.osm.pbf")
                        else:
                            input_file = input_maps_folder.joinpath("germany-latest.osm.pbf")

                    case "ESP":
                        input_file = input_maps_folder.joinpath("spain-latest.osm.pbf")

                    case "BEL":
                        input_file = input_maps_folder.joinpath("belgium-latest.osm.pbf")

                    case "CHN":
                        input_file = input_maps_folder.joinpath("china-latest.osm.pbf")

                    case "USA":
                        match entry["City"]:
                            case "NewYork":
                                input_file = input_maps_folder.joinpath("new-york-latest.osm.pbf")

                            case "Washington":
                                input_file = input_maps_folder.joinpath("district-of-columbia-latest.osm.pbf")

                            case "Austin":
                                input_file = input_maps_folder.joinpath("texas-latest.osm.pbf")

                            case "Phoenix":
                                input_file = input_maps_folder.joinpath("arizona-latest.osm.pbf")

                            case _:
                                execute_osmium = False
                                logging.warning(
                                    f"OSM file extraction for {entry['Country']} not automated. Do by hand! \n"
                                    f"This is the terminal command: \n"
                                    f"osmium extract --bbox {bbox_str(entry)} -o {output_file} input_file"
                                )

                    case "FRA":
                        input_file = input_maps_folder.joinpath("france-latest.osm.pbf")

                    case _:
                        execute_osmium = False
                        logging.warning(
                            f"OSM file extraction for {entry['Country']} not automated. Do by hand! \n"
                            f"This is the terminal command: \n"
                            f"osmium extract --bbox {bbox_str(entry)} -o {output_file} input_file"
                        )

                if execute_osmium:
                    logging.info(f"Extracting {entry['Country']}_{entry['City']}")
                    overwr = "--overwrite" if overwrite else ""
                    os.system(f"osmium extract --bbox {bbox_str(entry)} -o {output_file} {input_file} {overwr}")
                    # if not, the converted file is (almost) empty -- conversion was not successful
                    assert os.path.getsize(output_file) > 200

            except FileNotFoundError:
                logging.warning(f"Could not find input file {input_file}. Skipping...")
                logging.info("Download the file from https://download.geofabrik.de/ and place it in input_maps/")
                continue

    return output_folder
