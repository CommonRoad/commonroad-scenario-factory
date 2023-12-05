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
        match entry["Country"]:
            case  "Germany":
                input_file = Path("input/germany-latest.osm.pbf")
                os.system(f"osmium extract --bbox {bbox_str(entry)} -o {output_file} {input_file}")

            case _:
                logging.warning(f"OSM file extraction for {entry['Country']} not automated. Do by hand! \n"
                                f"This is the terminal command: \n"
                                f"osmium extract --bbox {bbox_str(entry)} -o {output_file} input_file")