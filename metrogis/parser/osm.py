"""
MetroGIS OSM Parser

解析 Overpass 返回的 OSM 数据
"""


from metrogis.models.subway import (
    Station,
    SubwayLine
)



def parse_osm_subway(
    data: dict,
    city: str = "大连"
):
    """
    将 Overpass JSON
    转换成 SubwayLine
    """

    line = SubwayLine(
        name="",
        city=city
    )


    elements = data.get(
        "elements",
        []
    )


    for element in elements:

        tags = element.get(
            "tags",
            {}
        )


        # relation线路
        if (
            element.get("type") == "relation"
            and tags.get("route") == "subway"
        ):

            line.name = tags.get(
                "name",
                ""
            )


        # station节点
        if element.get(
            "type"
        ) == "node":

            name = tags.get(
                "name"
            )


            if name:

                station = Station(

                    name=name,

                    lat=element.get(
                        "lat",
                        0
                    ),

                    lng=element.get(
                        "lon",
                        0
                    )

                )


                line.add_station(
                    station
                )


                line.add_point(
                    station.lng,
                    station.lat
                )


    return line