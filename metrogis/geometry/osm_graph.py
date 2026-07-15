"""
MetroGIS OSM Graph

将 OSM way 转换为线路拓扑图

用于:

    - 最短路径搜索
    - 轨迹还原
    - 线路计算

distance 使用真实米制距离
"""


from pyproj import Transformer



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
    计算两个经纬度点距离

    输入:

    [
        lng,
        lat
    ]


    返回:

    米
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





def build_osm_graph(
    tracks
):
    """
    构建 OSM Graph


    输入:

    [
        {
            id,
            nodes,
            geometry
        }
    ]



    返回:

    {
        node_id:

        {
            point:

            [
                lng,
                lat
            ],


            edges:

            [
                {
                    node:
                    distance
                }
            ]

        }
    }


    distance:
        米

    """


    graph = {}



    for track in tracks:


        nodes = track.get(
            "nodes",
            []
        )


        geometry = track.get(
            "geometry",
            []
        )



        #
        # 数据异常跳过
        #
        if len(nodes) < 2:

            continue



        if len(nodes) != len(geometry):

            continue




        for i in range(
            len(nodes)-1
        ):


            node_a = nodes[i]

            node_b = nodes[i+1]



            point_a = geometry[i]

            point_b = geometry[i+1]



            distance = point_distance(
                point_a,
                point_b
            )



            #
            # 创建节点
            #

            if node_a not in graph:

                graph[node_a] = {

                    "point":
                        point_a,

                    "edges":
                        []

                }



            if node_b not in graph:

                graph[node_b] = {

                    "point":
                        point_b,

                    "edges":
                        []

                }



            #
            # 双向边
            #

            graph[node_a]["edges"].append(
                {

                    "node":
                        node_b,

                    "distance":
                        round(
                            distance,
                            2
                        )

                }
            )



            graph[node_b]["edges"].append(
                {

                    "node":
                        node_a,

                    "distance":
                        round(
                            distance,
                            2
                        )

                }
            )



    return graph