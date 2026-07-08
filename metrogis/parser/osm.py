"""
MetroGIS OSM Parser
"""

from metrogis.models.subway import (
    SubwayLine,
    Station
)



def parse_osm_subway(
    data: dict,
    city: str = "大连"
):

    elements = data.get(
        "elements",
        []
    )


    nodes = {}

    ways = {}

    relations = []



    anonymous_nodes = []



    for element in elements:


        etype = element.get(
            "type"
        )


        eid = element.get(
            "id"
        )


        if etype == "node":


            if eid:

                nodes[eid] = element

            else:

                anonymous_nodes.append(
                    element
                )



        elif etype == "way":


            if eid:

                ways[eid] = element



        elif etype == "relation":


            relations.append(
                element
            )



    line_name = ""


    if relations:


        line_name = relations[0].get(
            "tags",
            {}
        ).get(
            "name",
            ""
        )



    line = SubwayLine(

        name=line_name,

        city=city

    )



    geometry = []

    stations = []



    # =====================
    # 解析所有 way geometry
    # =====================


    for way in ways.values():


        if way.get(
            "geometry"
        ):


            for point in way["geometry"]:


                geometry.append(

                    [

                        point.get(
                            "lon"
                        ),

                        point.get(
                            "lat"
                        )

                    ]

                )



        elif way.get(
            "nodes"
        ):


            for nid in way["nodes"]:


                node = nodes.get(
                    nid
                )


                if node:


                    geometry.append(

                        [

                            node.get(
                                "lon"
                            ),

                            node.get(
                                "lat"
                            )

                        ]

                    )



    # =====================
    # relation station node
    # =====================


    for relation in relations:


        for member in relation.get(
            "members",
            []
        ):


            if member.get(
                "type"
            ) != "node":

                continue



            node = nodes.get(
                member.get(
                    "ref"
                )
            )


            if not node:

                continue



            name = node.get(
                "tags",
                {}
            ).get(
                "name"
            )


            if name:


                stations.append(

                    Station(

                        name=name,

                        lat=node.get(
                            "lat",
                            0
                        ),

                        lng=node.get(
                            "lon",
                            0
                        )

                    )

                )



    # =====================
    # 兼容测试数据
    # =====================


    if not stations:


        for node in anonymous_nodes:


            name = node.get(
                "tags",
                {}
            ).get(
                "name"
            )


            if name:


                stations.append(

                    Station(

                        name=name,

                        lat=node.get(
                            "lat",
                            0
                        ),

                        lng=node.get(
                            "lon",
                            0
                        )

                    )

                )



    line.geometry = geometry

    line.stations = stations



    return line