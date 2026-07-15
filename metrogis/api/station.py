"""
MetroGIS Station API

负责查询 OpenStreetMap 地铁站点
"""

from .overpass import query_overpass
from ..resources.loader import get_station_list
from ..parser.station_matcher import match_station



def build_station_query(
    city_bbox
):
    """
    构建 OSM 地铁站查询

    city_bbox:

    south,west,north,east

    """


    south, west, north, east = city_bbox


    return f"""

[out:json][timeout:180];


(
    
node
[
    railway="station"
]
[
    station="subway"
]
({south},{west},{north},{east});


node
[
    railway="station"
]
[
    subway="yes"
]
({south},{west},{north},{east});


);


out body;

"""





def get_osm_stations(
    bbox
):
    """
    获取城市全部 OSM 地铁站
    """


    query = build_station_query(
        bbox
    )


    data = query_overpass(
        query
    )


    stations = []


    for element in data.get(
        "elements",
        []
    ):


        tags = element.get(
            "tags",
            {}
        )


        name = tags.get(
            "name"
        )


        if not name:

            continue



        stations.append(

            {

                "name": name,

                "lat": element.get(
                    "lat"
                ),

                "lng": element.get(
                    "lon"
                )

            }

        )


    return stations





def get_line_stations(
    city,
    line,
    bbox
):
    """
    获取指定线路运营站点对应的 OSM 坐标


    参数:

    city:
        天津


    line:
        3号线


    bbox:
        城市范围


    返回:

    [
        {
          name:
          lat:
          lng:
        }
    ]

    """



    # 运营顺序

    official_stations = get_station_list(
        city,
        line
    )


    if not official_stations:

        raise RuntimeError(
            f"没有找到线路数据: {city} {line}"
        )



    # OSM全部站点

    osm_stations = get_osm_stations(
        bbox
    )



    result = []



    for name in official_stations:


        station = match_station(
            name,
            osm_stations
        )


        if station:


            result.append(

                {

                    "official_name": name,

                    "osm_name": station["name"],

                    "lat": station["lat"],

                    "lng": station["lng"]

                }

            )


    return result