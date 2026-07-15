"""
MetroGIS Route Builder V5

基于 OSM Graph 构建线路轨迹

功能:

1. 使用 OSM node 拓扑
2. 最近节点匹配
3. Dijkstra 最短路径
4. 输出 TrackPoint
5. 米制距离计算

"""


from pyproj import Transformer


from metrogis.api.track import (
    get_track_geometry
)


from metrogis.geometry.osm_graph import (
    build_osm_graph
)


from metrogis.geometry.path_finder import (
    nearest_node,
    shortest_path,
    path_geometry
)





#
# 经纬度 -> 米
#

transformer = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:3857",
    always_xy=True
)







def point_distance(
    a,
    b
):
    """
    两点距离 米
    """


    ax, ay = transformer.transform(
        a[0],
        a[1]
    )


    bx, by = transformer.transform(
        b[0],
        b[1]
    )


    return (
        (ax-bx)**2 +
        (ay-by)**2
    ) ** 0.5







def geometry_length(
    geometry
):
    """
    计算轨迹长度
    """


    total = 0


    for i in range(
        len(geometry)-1
    ):


        total += point_distance(
            geometry[i],
            geometry[i+1]
        )


    return total







def build_route_geometry(
    line,
    bbox
):
    """
    根据线路站点生成完整轨迹


    参数:

        line:
            Line对象


        bbox:
            Overpass范围


    返回:

        Line

    """



    print(
        "获取OSM轨迹..."
    )


    #
    # 获取OSM轨迹
    #

    tracks = get_track_geometry(
        bbox
    )


    print(
        "轨迹数量:",
        len(tracks)
    )




    #
    # 构建Graph
    #

    print(
        "构建OSM Graph..."
    )


    graph = build_osm_graph(
        tracks
    )



    print(
        "节点数量:",
        len(graph)
    )





    route = []





    stations = line.stations





    for i in range(
        len(stations)-1
    ):


        start_station = stations[i]

        end_station = stations[i+1]



        start_point = [

            start_station.lng,

            start_station.lat

        ]



        end_point = [

            end_station.lng,

            end_station.lat

        ]




        print()

        print(
            "路径:",
            start_station.name,
            "->",
            end_station.name
        )




        #
        # 最近节点
        #

        start_node = nearest_node(
            graph,
            start_point
        )


        end_node = nearest_node(
            graph,
            end_point
        )



        if (
            start_node is None
            or
            end_node is None
        ):


            print(
                "节点匹配失败"
            )

            continue






        #
        # 最短路径
        #

        path = shortest_path(
            graph,
            start_node,
            end_node
        )



        if not path:


            print(
                "没有找到路径"
            )


            continue




        geometry = path_geometry(
            graph,
            path
        )



        print(
            "节点:",
            len(path),
            "轨迹点:",
            len(geometry)
        )





        #
        # 合并线路
        #

        if route:


            route.extend(
                geometry[1:]
            )


        else:


            route.extend(
                geometry
            )






    #
    # 总长度
    #

    total = geometry_length(
        route
    )


    print()

    print(
        "线路长度:",
        round(
            total,
            2
        ),
        "米"
    )






    #
    # 写入 TrackPoint
    #

    line.geometry=[]



    distance = 0




    for i,p in enumerate(
        route
    ):



        if i > 0:


            distance += point_distance(
                route[i-1],
                p
            )



        line.add_geometry_point(

            p[0],

            p[1],

            round(
                distance,
                2
            )

        )





    print(
        "最终轨迹点:",
        len(line.geometry)
    )



    return line