"""
MetroGIS Station Order

根据线路 geometry 对车站进行排序

用途:
将 OSM 返回的无序 station
按照真实线路方向排序
"""


import math



def distance(
    p1,
    p2
):
    """
    简单经纬度距离
    """

    return math.sqrt(

        (p1[0] - p2[0]) ** 2

        +

        (p1[1] - p2[1]) ** 2

    )




def nearest_geometry_index(
    station,
    geometry
):
    """
    找车站距离线路最近的点
    """

    target = [

        station.lng,

        station.lat

    ]


    min_distance = float(
        "inf"
    )


    index = 0



    for i, point in enumerate(
        geometry
    ):


        d = distance(
            target,
            point
        )


        if d < min_distance:


            min_distance = d

            index = i



    return index




def sort_stations_by_geometry(
    stations,
    geometry
):
    """
    根据线路方向排序车站

    geometry:
        [
            [lng,lat],
            [lng,lat]
        ]

    返回:
        排序后的 stations
    """


    if not geometry:

        return stations



    result = []



    for station in stations:


        index = nearest_geometry_index(

            station,

            geometry

        )


        result.append(

            (

                index,

                station

            )

        )



    result.sort(

        key=lambda x:x[0]

    )


    return [

        x[1]

        for x in result

    ]
