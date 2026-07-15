"""
MetroGIS OSM Path Finder

基于 OSM graph
寻找两个车站之间真实轨迹
"""


import heapq


from metrogis.geometry.route_builder import (
    point_distance
)



def nearest_node(
    graph,
    point
):
    """
    找最近OSM节点

    point:
        [lng,lat]
    """

    best = None
    distance = float(
        "inf"
    )


    for node,data in graph.items():

        d = point_distance(
            data["point"],
            point
        )


        if d < distance:

            distance = d
            best = node


    return best



def shortest_path(
    graph,
    start,
    end
):
    """
    Dijkstra

    返回:
        node列表
    """


    queue = [
        (
            0,
            start
        )
    ]


    visited = {}


    parent = {}



    while queue:


        cost,node = heapq.heappop(
            queue
        )


        if node in visited:
            continue


        visited[node]=cost



        if node == end:
            break



        for edge in graph[node]["edges"]:

            nxt = edge["node"]

            new_cost = (
                cost+
                edge["distance"]
            )


            if nxt not in visited:

                heapq.heappush(
                    queue,
                    (
                        new_cost,
                        nxt
                    )
                )


                parent[nxt]=node



    if end not in visited:

        return []



    path=[]


    node=end


    while node != start:

        path.append(
            node
        )

        node=parent[node]


    path.append(
        start
    )


    path.reverse()


    return path



def path_geometry(
    graph,
    path
):
    """
    node路径转坐标
    """


    result=[]


    for node in path:

        result.append(
            graph[node]["point"]
        )


    return result