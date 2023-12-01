Open street map data can be downloaded from [geofabrik.de](https://download.geofabrik.de/). 

To extract certain parts of large-scale map, use
```bash
osmium extract -b=left,bottom,right,top -o=output_file.osm input_file.osm.pbf
```
replacing left etc. with coordinates. This can also be triggered directly from Python
```python
# input parameters
bounding_box = "11.56714,48.14778,11.56199,48.15335"
output_osm_file = "../files/DEU_Maxvorstadt-1.osm"
input_file = "../files/oberbayern-latest.osm"
commonroad_file = "../files/DEU_Maxvorstadt-1.xml"
output_dir = "../files/intersections"

# load map
os.system(f"osmium extract --bbox {bounding_box} -o {output_osm_file} {input_file}")
```
