"""
MetroGIS OSM Graph

将 OSM way 转换为线路拓扑图

用于:
    最短路径搜索
"""


from math import sqrt





def point_distance(
    a,
    b
):
    """
    经纬度简单距离

    后续可以替换 EPSG3857

    """

    return sqrt(
        (a[0]-b[0]) ** 2
        +
        (a[1]-b[1]) ** 2
    )







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
          "point":
          [
            lng,
            lat
          ],

          "edges":
          [
             {
              node,
              distance
             }
          ]
        }
    }

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
            # 保存节点
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
            # 双向连接
            #

            graph[node_a]["edges"].append(
                {

                    "node":
                        node_b,

                    "distance":
                        distance

                }
            )



            graph[node_b]["edges"].append(
                {

                    "node":
                        node_a,

                    "distance":
                        distance

                }
            )


    return graph