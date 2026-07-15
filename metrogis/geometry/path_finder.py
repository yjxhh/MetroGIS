"""
MetroGIS Path Finder

基于 OSM Graph
进行线路路径搜索

功能:

1. 最近节点搜索
2. 最短路径
3. 节点转轨迹
"""


import heapq



from math import sqrt





def point_distance(
    a,
    b
):
    """
    经纬度距离

    这里只用于节点匹配

    """

    return sqrt(
        (a[0]-b[0]) ** 2
        +
        (a[1]-b[1]) ** 2
    )







def nearest_node(
    graph,
    point
):
    """
    查找距离坐标最近的 OSM node


    point:

    [
        lng,
        lat
    ]

    返回:

    node_id

    """


    nearest = None

    minimum = float(
        "inf"
    )


    for node,data in graph.items():


        d = point_distance(
            data["point"],
            point
        )


        if d < minimum:

            minimum = d

            nearest = node



    return nearest







def find_shortest_path(
    graph,
    start,
    end
):
    """
    Dijkstra 最短路径


    start:

        node id


    end:

        node id


    返回:

        [
          node1,
          node2,
          ...
        ]

    """


    queue = []


    heapq.heappush(
        queue,
        (
            0,
            start
        )
    )


    distance = {

        start:0

    }


    previous = {}



    while queue:


        current_distance,current = heapq.heappop(
            queue
        )



        if current == end:

            break



        if current_distance > distance.get(
            current,
            float("inf")
        ):

            continue




        for edge in graph[current]["edges"]:


            neighbor = edge["node"]


            weight = edge["distance"]


            new_distance = (
                current_distance
                +
                weight
            )


            if new_distance < distance.get(
                neighbor,
                float("inf")
            ):


                distance[neighbor] = new_distance


                previous[neighbor] = current


                heapq.heappush(
                    queue,
                    (
                        new_distance,
                        neighbor
                    )
                )




    #
    # 回溯路径
    #

    if end not in previous and start != end:

        return []



    path = [

        end

    ]


    current = end



    while current != start:


        current = previous[current]


        path.append(
            current
        )



    path.reverse()



    return path







def path_to_geometry(
    graph,
    path
):
    """
    node路径转经纬度


    返回:

    [
       [lng,lat],
       ...
    ]

    """


    result = []


    for node in path:


        result.append(
            graph[node]["point"]
        )


    return result
def shortest_path(
    graph,
    start,
    end
):
    """
    shortest_path 兼容接口

    调用 Dijkstra
    """

    return find_shortest_path(
        graph,
        start,
        end
    )
def path_geometry(
    graph,
    path
):
    """
    path_geometry 兼容接口

    node路径转换为经纬度轨迹

    返回:

    [
        [lng,lat],
        ...
    ]

    """

    return path_to_geometry(
        graph,
        path
    )
def find_path(
    graph,
    start,
    end
):
    """
    find_path 兼容接口

    调用最短路径搜索
    """

    return shortest_path(
        graph,
        start,
        end
    )