"""
MetroGIS Transit Models

城市轨道交通数据模型

支持:

City
Network
Line
Station
TrackPoint

"""


from dataclasses import dataclass, field

from typing import List, Optional





@dataclass
class City:
    """
    城市
    """

    id: str

    name: str

    country: str = "China"

    province: Optional[str] = None





@dataclass
class Network:
    """
    轨道交通网络

    例如:

    北京地铁
    天津轨道交通

    """

    id: str

    name: str

    city: City

    operator: Optional[str] = None

    lines: List["Line"] = field(
        default_factory=list
    )





@dataclass
class TrackPoint:
    """
    线路轨迹点


    lng:
        经度


    lat:
        纬度


    distance:
        从线路起点累计距离(米)

    """

    lng: float

    lat: float

    distance: float = 0





@dataclass
class Station:
    """
    地铁车站
    """

    id: str

    name: str

    lat: float

    lng: float


    sequence: int = 0


    lines: List["Line"] = field(
        default_factory=list
    )


    interchange: bool = False





@dataclass
class Line:
    """
    地铁线路


    例如:

    天津地铁3号线


    """

    id: str

    name: str


    network: Network


    ref: Optional[str] = None


    route_type: str = "subway"



    relations: List = field(
        default_factory=list
    )



    stations: List[Station] = field(
        default_factory=list
    )



    geometry: List[TrackPoint] = field(
        default_factory=list
    )



    directions: int = 0



    variants: List = field(
        default_factory=list
    )





    def add_station(
        self,
        station: Station
    ):

        """
        添加站点

        自动建立双向关系
        """


        self.stations.append(
            station
        )


        if self not in station.lines:

            station.lines.append(
                self
            )



        if len(
            station.lines
        ) > 1:

            station.interchange = True





    def add_geometry_point(
        self,
        lng,
        lat,
        distance=0
    ):

        """
        添加轨迹点
        """


        self.geometry.append(

            TrackPoint(

                lng=lng,

                lat=lat,

                distance=distance

            )

        )





    def station_names(
        self
    ):

        """
        获取线路站名

        """

        return [

            s.name

            for s in self.stations

        ]