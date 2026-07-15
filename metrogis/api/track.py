"""
MetroGIS Track API V2

获取 OSM railway track geometry

功能:

1. Overpass 查询 railway way
2. 返回 node
3. 返回 geometry
4. 保存 OSM tags 信息

"""


from metrogis.api.overpass import (
    query_overpass
)





def build_track_query(
    bbox
):
    """
    构造 Overpass 查询


    bbox:

    south,
    west,
    north,
    east

    """


    south, west, north, east = bbox


    query = f"""
    [out:json];

    (
      way
      ["railway"="subway"]
      ({south},{west},{north},{east});

      way
      ["railway"="light_rail"]
      ({south},{west},{north},{east});

      way
      ["railway"="rail"]
      ({south},{west},{north},{east});
    );

    out geom;
    """


    return query







def normalize_tags(
    tags
):
    """
    提取常用字段
    """


    if not tags:

        tags={}



    return {

        "tags":
            tags,


        "name":
            tags.get(
                "name"
            ),


        "railway":
            tags.get(
                "railway"
            ),


        "service":
            tags.get(
                "service"
            ),


        "operator":
            tags.get(
                "operator"
            ),


        "layer":
            tags.get(
                "layer"
            ),


        "bridge":
            tags.get(
                "bridge"
            ),


        "tunnel":
            tags.get(
                "tunnel"
            )

    }








def get_track_geometry(
    bbox
):
    """
    获取 OSM轨迹


    返回:

    [

      {

        id,

        nodes,

        geometry,

        tags,

        railway,

        name

      }

    ]

    """


    query = build_track_query(
        bbox
    )


    data = query_overpass(
        query
    )


    tracks=[]



    for element in data.get(
        "elements",
        []
    ):


        if element.get(
            "type"
        ) != "way":

            continue



        geometry=[]


        nodes=[]



        for point in element.get(
            "geometry",
            []
        ):


            geometry.append(

                [

                    point["lon"],

                    point["lat"]

                ]

            )



        for node in element.get(
            "nodes",
            []
        ):

            nodes.append(
                node
            )



        if len(nodes)<2:

            continue



        track = {


            "id":
                element["id"],


            "nodes":
                nodes,


            "geometry":
                geometry,


            **normalize_tags(
                element.get(
                    "tags",
                    {}
                )
            )

        }



        tracks.append(
            track
        )



    return tracks