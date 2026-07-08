from dataclasses import dataclass, field



@dataclass
class Station:

    name: str

    lat: float | None = None

    lng: float | None = None



@dataclass
class SubwayLine:

    name: str

    stations: list[Station] = field(
        default_factory=list
    )

    geometry: list = field(
        default_factory=list
    )



def clean_geometry(
    geometry
):
    """
    去除连续重复坐标

    保持线路顺序
    """

    if not geometry:

        return []


    result = []


    last = None


    for point in geometry:


        if point == last:

            continue


        result.append(
            point
        )


        last = point


    return result



def parse_osm_subway(
    data,
    city=None
):

    elements = data.get(
        "elements",
        []
    )


    relation = None

    nodes = {}

    ways = {}



    # 建立索引

    for element in elements:

        etype = element.get(
            "type"
        )


        if etype == "node":

            nodes[
                element["id"]
            ] = element


        elif etype == "way":

            ways[
                element["id"]
            ] = element



    # 查找线路

    for element in elements:

        if element.get(
            "type"
        ) != "relation":

            continue


        tags = element.get(
            "tags",
            {}
        )


        if tags.get(
            "route"
        ) in (
            "subway",
            "light_rail",
            "railway"
        ):

            relation = element

            break



    if relation is None:

        return SubwayLine(
            name="Unknown"
        )



    tags = relation.get(
        "tags",
        {}
    )


    line_name = tags.get(
        "name",
        "Unknown"
    )



    stations = []

    geometry = []



    # 解析站点

    for member in relation.get(
        "members",
        []
    ):


        if (

            member.get("type")
            == "node"

            and

            member.get("role")
            == "stop"

        ):


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
                            "lat"
                        ),

                        lng=node.get(
                            "lon"
                        )

                    )

                )



    # 解析线路

    for member in relation.get(
        "members",
        []
    ):


        if member.get(
            "type"
        ) != "way":

            continue



        way = ways.get(
            member.get(
                "ref"
            )
        )


        if not way:

            continue



        for node_id in way.get(
            "nodes",
            []
        ):


            node = nodes.get(
                node_id
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



    # 清理重复点

    geometry = clean_geometry(
        geometry
    )



    return SubwayLine(

        name=line_name,

        stations=stations,

        geometry=geometry

    )