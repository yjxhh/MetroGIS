"""
MetroGIS Path Finder V2

基于 OSM Graph

功能:

1. KDTree最近节点搜索
2. Dijkstra最短路径
3. node转geometry
4. 路径距离计算
"""


import heapq


from math import sqrt


try:

    from scipy.spatial import KDTree

    SCIPY_AVAILABLE = True

except ImportError:

    SCIPY_AVAILABLE = False





def point_distance(
    a,
    b
):
    """
    经纬度距离

    """

    return sqrt(
        (a[0]-b[0]) ** 2
        +
        (a[1]-b[1]) ** 2
    )





class SpatialIndex:
    """
    OSM Graph空间索引

    """

    def __init__(
        self,
        graph
    ):

        self.graph = graph


        self.nodes=[]

        self.points=[]



        for node,data in graph.items():

            self.nodes.append(
                node
            )

            self.points.append(
                data["point"]
            )



        if SCIPY_AVAILABLE:


            self.tree = KDTree(
                self.points
            )


        else:

            self.tree=None






    def nearest(
        self,
        point
    ):
        """
        最近节点
        """

        if self.tree:


            distance,index = self.tree.query(
                point
            )


            return self.nodes[index]



        #
        # fallback
        #

        nearest=None

        minimum=float(
            "inf"
        )


        for node,p in zip(
            self.nodes,
            self.points
        ):


            d=point_distance(
                p,
                point
            )


            if d < minimum:

                minimum=d

                nearest=node



        return nearest







def build_spatial_index(
    graph
):
    """
    创建空间索引
    """

    return SpatialIndex(
        graph
    )







def nearest_node(
    graph,
    point,
    index=None
):
    """
    查找最近OSM节点


    point:

    [
      lng,
      lat
    ]

    """



    if index is None:


        index = build_spatial_index(
            graph
        )



    return index.nearest(
        point
    )









def find_shortest_path(
    graph,
    start,
    end
):
    """
    Dijkstra

    """

    queue=[]


    heapq.heappush(
        queue,
        (
            0,
            start
        )
    )


    distance={

        start:0

    }


    previous={}



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


            neighbor=edge["node"]


            weight=edge["distance"]



            new_distance = (
                current_distance
                +
                weight
            )


            if new_distance < distance.get(
                neighbor,
                float("inf")
            ):


                distance[neighbor]=new_distance


                previous[neighbor]=current



                heapq.heappush(
                    queue,
                    (
                        new_distance,
                        neighbor
                    )
                )




    if end not in previous and start != end:

        return []



    path=[end]


    current=end



    while current != start:


        current=previous[current]


        path.append(
            current
        )


    path.reverse()


    return path








def shortest_path(
    graph,
    start,
    end
):

    return find_shortest_path(
        graph,
        start,
        end
    )







def path_to_geometry(
    graph,
    path
):
    """
    node -> 经纬度
    """


    result=[]


    for node in path:


        result.append(
            graph[node]["point"]
        )


    return result








def path_geometry(
    graph,
    path
):

    return path_to_geometry(
        graph,
        path
    )








def find_path(
    graph,
    start_node,
    end_node
):
    """
    返回带距离信息路径

    """

    path=find_shortest_path(
        graph,
        start_node,
        end_node
    )


    result=[]


    total=0



    for i,node in enumerate(path):


        point=graph[node]["point"]



        if i>0:

            total += point_distance(
                graph[path[i-1]]["point"],
                point
            )



        result.append(

            {
                "node":node,

                "point":point,

                "distance":round(
                    total,
                    2
                )
            }

        )


    return result