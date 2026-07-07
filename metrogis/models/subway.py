"""
MetroGIS Subway Models

定义地铁线路和车站的数据结构
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Station:
    """
    地铁车站
    """

    name: str

    lat: float

    lng: float

    order: int = 0



@dataclass
class SubwayLine:
    """
    地铁线路
    """

    name: str

    city: str = ""

    stations: List[Station] = field(
        default_factory=list
    )

    geometry: List[list] = field(
        default_factory=list
    )


    def add_station(
        self,
        station: Station
    ):
        """
        添加车站
        """

        self.stations.append(
            station
        )


    def add_point(
        self,
        lng: float,
        lat: float
    ):
        """
        添加线路坐标点
        """

        self.geometry.append(
            [
                lng,
                lat
            ]
        )