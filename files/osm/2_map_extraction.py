import logging
import os
import pandas as pd
from pathlib import Path
from pandas import Series

with open(Path("0_cities_selected.csv"), newline='') as csvfile:
    cities = pd.read_csv(csvfile)

    def bbox_str(entry: Series) -> str:
        return f"{entry['West']},{entry['South']},{entry['East']},{entry['North']}"


    for row, entry in cities.iterrows():
        output_file = Path(f"output/{entry['Country']}_{entry['City']}.osm")
        execute_osmium = True
        match entry["Country"]:
            case "DEU":
                input_file = Path("input/germany-latest.osm.pbf")

            case "ESP":
                input_file = Path("input/spain-latest.osm.pbf")

            case "BEL":
                input_file = Path("input/belgium-latest.osm.pbf")

            case _:
                execute_osmium = False
                logging.warning(f"OSM file extraction for {entry['Country']} not automated. Do by hand! \n"
                                f"This is the terminal command: \n"
                                f"osmium extract --bbox {bbox_str(entry)} -o {output_file} input_file")

        if execute_osmium:
            os.system(f"osmium extract --bbox {bbox_str(entry)} -o {output_file} {input_file}")