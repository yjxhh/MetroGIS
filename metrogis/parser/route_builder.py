"""
MetroGIS Route Builder

负责:

官方线路顺序
+
OSM站点坐标
+
人工补充坐标

生成标准 Line 对象
"""


from metrogis.resources.loader import (
    get_station_list
)


from metrogis.resources.override import (
    get_override_station
)


from metrogis.api.station import (
    get_line_stations
)


from metrogis.models.transit import (
    City,
    Network,
    Line,
    Station
)


from metrogis.parser.station_matcher import (
    match_station
)



def create_route(
    city_name: str,
    line_name: str,
    bbox,
    city_id: str = None,
    network_id: str = None
):
    """
    创建线路对象

    Parameters
    ----------
    city_name:
        城市

    line_name:
        线路名称

    bbox:
        查询范围


    Returns
    -------
    Line
    """


    #
    # 官方站点顺序
    #

    official_stations = get_station_list(
        city_name,
        line_name
    )


    #
    # OSM站点
    #

    osm_stations = get_line_stations(
        city_name,
        line_name,
        bbox
    )


    #
    # 创建基础对象
    #

    city = City(
        id=city_id or city_name,
        name=city_name
    )


    network = Network(
        id=network_id or city_name,
        name=f"{city_name}轨道交通",
        city=city
    )


    line = Line(
        id=f"{city_name}_{line_name}",
        name=f"{city_name}{line_name}",
        network=network
    )


    #
    # 按官方顺序生成
    #

    sequence = 1


    for station_name in official_stations:


        #
        # 优先匹配 OSM
        #

        matched = match_station(
            station_name,
            osm_stations
        )


        if matched:


            station = Station(

                id=f"{city_name}_{station_name}",

                name=station_name,

                lat=matched["lat"],

                lng=matched["lng"],

                sequence=sequence

            )


        else:


            #
            # OSM没有
            # 查询补充
            #

            override = get_override_station(

                city_name,

                line_name,

                station_name

            )


            if override is None:


                print(
                    "缺少坐标:",
                    city_name,
                    line_name,
                    station_name
                )


                sequence += 1

                continue



            station = Station(

                id=f"{city_name}_{station_name}",

                name=station_name,

                lat=override["lat"],

                lng=override["lng"],

                sequence=sequence

            )


        line.add_station(
            station
        )


        sequence += 1



    return line
