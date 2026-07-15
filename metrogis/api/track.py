"""
MetroGIS Track API

负责从 OpenStreetMap 获取
地铁运行轨迹 geometry

升级:
1. 保留 way id
2. 保留 node 拓扑关系
3. 支持 Graph 构建
"""


from .overpass import query_overpass





def build_track_query(
    bbox
):
    """
    构造轨道查询
    """


    south, west, north, east = bbox


    return f"""

[out:json][timeout:180];


(
    
way
[
 railway="subway"
]
({south},{west},{north},{east});


way
[
 railway="light_rail"
]
({south},{west},{north},{east});


);


out geom;


"""





def get_track_geometry(
    bbox
):
    """
    获取 OSM 轨迹


    返回:

    [
        {
            id,
            nodes,
            geometry
        }
    ]

    """


    query = build_track_query(
        bbox
    )


    data = query_overpass(
        query
    )


    result = []


    for element in data.get(
        "elements",
        []
    ):


        geometry = element.get(
            "geometry"
        )


        if not geometry:

            continue



        points = []


        for point in geometry:


            points.append(
                [
                    point["lon"],
                    point["lat"]
                ]
            )



        #
        # OSM way 节点
        #
        nodes = element.get(
            "nodes",
            []
        )



        result.append(
            {

                "id":
                    element.get(
                        "id"
                    ),


                "nodes":
                    nodes,


                "geometry":
                    points

            }
        )


    return result