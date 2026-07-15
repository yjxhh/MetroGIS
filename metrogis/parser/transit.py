"""
MetroGIS Transit Parser

负责:

OSM 数据
    +
线路运营站点顺序

转换为:

Transit Model

"""

from metrogis.models.transit import (
    City,
    Network,
    Line,
    Station,
    Relation
)



def create_line(
    city: City,
    network: Network,
    line_id: str,
    name: str,
    ref: str = None,
    route_type: str = "subway"
):
    """
    创建线路对象
    """

    line = Line(

        id=line_id,

        name=name,

        network=network,

        ref=ref,

        route_type=route_type

    )


    network.add_line(
        line
    )


    return line



def add_station_to_line(
    line: Line,
    station_id: str,
    name: str,
    lat: float,
    lng: float,
    sequence: int
):
    """
    添加线路站点

    sequence 来自运营顺序
    """

    station = Station(

        id=station_id,

        name=name,

        lat=lat,

        lng=lng,

        sequence=sequence

    )


    station.add_line(
        line
    )


    line.add_station(
        station
    )


    return station



def add_osm_relation(
    line: Line,
    relation_id: int,
    tags: dict
):
    """
    添加 OSM relation
    """

    relation = Relation(

        id=relation_id,

        tags=tags

    )


    line.add_relation(
        relation
    )


    return relation