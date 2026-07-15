"""
MetroGIS Route Builder V5

基于 OSM Graph 构建地铁线路轨迹


流程:

官方站点顺序
        |
        |
nearest OSM node
        |
        |
Dijkstra shortest path
        |
        |
node geometry
        |
        |
TrackPoint


功能:

1. 官方运营顺序
2. OSM拓扑路径
3. 最短路径搜索
4. 米制距离
5. TrackPoint输出
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
# 经纬度转米
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
    两个经纬度点距离
    单位: 米
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
        (ax-bx)**2
        +
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







def merge_geometry(
    old,
    new
):
    """
    合并两个区间轨迹

    去掉重复站点
    """


    if not old:

        return new



    if not new:

        return old



    return old + new[1:]









def add_track_points(
    line,
    geometry
):
    """
    写入 Line.geometry

    TrackPoint
    """


    line.geometry=[]


    distance = 0



    for i,p in enumerate(
        geometry
    ):


        if i > 0:


            distance += point_distance(

                geometry[i-1],

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



    return line







def build_route_geometry(
    line,
    bbox
):
    """
    根据官方站点顺序生成线路


    参数:

        line:
            Line对象


        bbox:
            (
              south,
              west,
              north,
              east
            )



    返回:

        Line
    """



    print(
        "获取OSM轨迹..."
    )



    tracks = get_track_geometry(
        bbox
    )



    print(
        "轨迹数量:",
        len(tracks)
    )





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



    route=[]



    stations = line.stations




    for i in range(
        len(stations)-1
    ):


        start_station = stations[i]

        end_station = stations[i+1]



        print()


        print(
            "路径:",
            start_station.name,
            "->",
            end_station.name
        )




        start_point=[

            start_station.lng,

            start_station.lat

        ]



        end_point=[

            end_station.lng,

            end_station.lat

        ]




        start_node = nearest_node(

            graph,

            start_point

        )


        end_node = nearest_node(

            graph,

            end_point

        )



        if start_node is None:


            print(
                "起点匹配失败:",
                start_station.name
            )

            continue



        if end_node is None:


            print(
                "终点匹配失败:",
                end_station.name
            )

            continue





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




        route = merge_geometry(

            route,

            geometry

        )






    print()


    length = geometry_length(
        route
    )


    print(
        "线路长度:",
        round(
            length,
            2
        ),
        "米"
    )



    print(
        "最终轨迹点:",
        len(route)
    )




    add_track_points(

        line,

        route

    )



    return line