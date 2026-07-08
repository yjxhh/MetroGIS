"""
下载地铁线路数据

示例:
python -m scripts.download_line
"""


from metrogis.api.overpass import (
    search_metro_line
)

from metrogis.parser.osm import (
    parse_osm_subway
)

from metrogis.exporter.geojson import (
    subway_to_geojson,
    save_geojson
)



def main():


    print(
        "Downloading 大连地铁13号线..."
    )



    data = search_metro_line(
        "13"
    )



    print(
        "Parse OSM data..."
    )



    line = parse_osm_subway(
        data,
        city="大连"
    )



    print(
        "Line:",
        line.name
    )



    print(
        "Stations:",
        len(line.stations)
    )



    print(
        "Geometry points:",
        len(line.geometry)
    )



    geojson = subway_to_geojson(
        line
    )



    save_geojson(

        geojson,

        "data/dalian_line13.geojson"

    )



    print(
        "Done: data/dalian_line13.geojson"
    )




if __name__ == "__main__":

    main()
