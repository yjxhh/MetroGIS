"""
MetroGIS OSM Graph

OSM轨迹转换为拓扑图

功能:

1. OSM way -> Graph
2. 经纬度米制距离
3. 节点合并
4. 断点修复
5. 最短路径支持

"""


from pyproj import Transformer

from scipy.spatial import KDTree





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
    经纬度距离(米)

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
            [lng,lat],

            edges:
            [
              {
                node,
                distance
              }
            ]
        }
    }


    """



    graph={}



    #
    # 第一阶段
    # 建立原始节点
    #

    print(
        "原始节点:",
        sum(
            len(
                t.get(
                    "nodes",
                    []
                )
            )
            for t in tracks
        )
    )



    for track in tracks:


        nodes=track.get(
            "nodes",
            []
        )


        geometry=track.get(
            "geometry",
            []
        )


        if len(nodes)<2:

            continue


        if len(nodes)!=len(geometry):

            continue



        for node,point in zip(
            nodes,
            geometry
        ):


            if node not in graph:


                graph[node]={

                    "point":point,

                    "edges":[]

                }






        #
        # 添加way边
        #

        for i in range(
            len(nodes)-1
        ):


            a=nodes[i]

            b=nodes[i+1]


            distance=point_distance(
                graph[a]["point"],
                graph[b]["point"]
            )


            graph[a]["edges"].append(

                {

                    "node":b,

                    "distance":distance

                }

            )


            graph[b]["edges"].append(

                {

                    "node":a,

                    "distance":distance

                }

            )





    print(
        "节点数量:",
        len(graph)
    )


    return graph








def merge_near_nodes(
    graph,
    threshold=2
):
    """
    合并距离非常近的节点

    threshold:

        米

    """



    ids=list(
        graph.keys()
    )


    points=[

        graph[i]["point"]

        for i in ids

    ]


    xy=[]


    for p in points:

        x,y=transformer.transform(
            p[0],
            p[1]
        )

        xy.append(
            [
                x,
                y
            ]
        )



    tree=KDTree(
        xy
    )


    mapping={}



    removed=set()



    for i,node in enumerate(ids):


        if node in removed:

            continue



        neighbors=tree.query_ball_point(

            xy[i],

            threshold

        )


        for n in neighbors:


            other=ids[n]


            if other==node:

                continue


            if other in removed:

                continue



            mapping[other]=node


            removed.add(
                other
            )





    #
    # 没有合并
    #

    if not mapping:


        print(
            "无节点合并"
        )

        return graph






    new_graph={}



    for node,data in graph.items():


        if node in mapping:

            continue


        new_graph[node]=data



    #
    # 更新边
    #

    for node,data in new_graph.items():


        edges=[]


        for e in data["edges"]:


            target=e["node"]


            if target in mapping:

                target=mapping[target]


            if target==node:

                continue


            edges.append(

                {

                    "node":target,

                    "distance":e["distance"]

                }

            )


        data["edges"]=edges




    print(
        "合并后节点:",
        len(new_graph)
    )


    return new_graph










def repair_graph_connections(
    graph,
    threshold=15
):
    """
    修复少量断点

    只处理:

    degree <= 1


    """



    ids=list(
        graph.keys()
    )


    points=[

        graph[i]["point"]

        for i in ids

    ]


    xy=[]


    for p in points:

        x,y=transformer.transform(
            p[0],
            p[1]
        )

        xy.append(
            [
                x,
                y
            ]
        )


    tree=KDTree(
        xy
    )



    repaired=0




    for index,node in enumerate(ids):


        #
        # 正常节点不处理
        #

        if len(
            graph[node]["edges"]
        )>1:

            continue



        neighbors=tree.query_ball_point(

            xy[index],

            threshold

        )



        for n in neighbors:


            other=ids[n]


            if other==node:

                continue



            exists=False


            for e in graph[node]["edges"]:

                if e["node"]==other:

                    exists=True

                    break



            if exists:

                continue



            d=point_distance(

                graph[node]["point"],

                graph[other]["point"]

            )



            graph[node]["edges"].append(

                {

                    "node":other,

                    "distance":d

                }

            )


            graph[other]["edges"].append(

                {

                    "node":node,

                    "distance":d

                }

            )


            repaired+=1


            break




    print(
        "修复断点:",
        repaired
    )



    return graph











def build_connected_osm_graph(
    tracks
):
    """
    完整建图入口

    """



    graph=build_osm_graph(
        tracks
    )


    graph=merge_near_nodes(
        graph
    )


    graph=repair_graph_connections(
        graph
    )


    return graph