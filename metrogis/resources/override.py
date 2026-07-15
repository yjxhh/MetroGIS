"""
MetroGIS Station Override

用于补充 OSM 缺失车站
"""


import yaml
from pathlib import Path



BASE_DIR = Path(__file__).parent



def load_station_override():

    file = (
        BASE_DIR
        /
        "station_override.yaml"
    )


    if not file.exists():

        return {}


    with open(
        file,
        "r",
        encoding="utf-8"
    ) as f:

        return yaml.safe_load(f) or {}



def get_override_station(
    city,
    line,
    station
):

    data = load_station_override()


    try:

        return (
            data
            [city]
            [line]
            [station]
        )


    except KeyError:

        return None