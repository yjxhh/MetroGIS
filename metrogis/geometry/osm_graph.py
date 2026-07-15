"""
MetroGIS OSM Graph V4.1

OSM way -> Graph

功能:

1. 节点拓扑
2. 米制距离
3. 保存 way metadata
4. railway 过滤
5. route 过滤
6. 去除重复 Edge
7. Edge 保存完整 metadata

用于:

- shortest path
- route builder
- metro geometry reconstruction
"""

from math import sqrt

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
    两点距离（米）
    """

    ax, ay = transformer.transform(
        a[0],
        a[1]
    )

    bx, by = transformer.transform(
        b[0],
        b[1]
    )

    return sqrt(
        (ax - bx) ** 2 +
        (ay - by) ** 2
    )


def check_filter(
    track,
    railway_filter=None,
    route_filter=None
):
    """
    判断 Way 是否保留
    """

    tags = track.get(
        "tags",
        {}
    )

    if railway_filter:

        railway = tags.get(
            "railway"
        )

        if railway != railway_filter:
            return False

    if route_filter:

        route = tags.get(
            "route"
        )

        if route != route_filter:
            return False

    return True


def build_osm_graph(
    tracks,
    railway_filter=None,
    route_filter=None
):
    """
    构建 OSM Graph

    graph =

    {
        node_id:
        {
            point:[lng,lat],

            edges:
            [
                {
                    node,
                    distance,
                    way,
                    tags
                }
            ]
        }
    }
    """

    print(
        "构建OSM Graph..."
    )

    graph = {}

    raw_nodes = 0

    used_ways = 0

    #
    # 防止重复 Edge
    #
    edge_cache = set()

    for track in tracks:

        if not check_filter(
            track,
            railway_filter,
            route_filter
        ):
            continue

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

        used_ways += 1

        #
        # 每条 Way 独立复制 tags
        #
        tags = dict(
            track.get(
                "tags",
                {}
            )
        )

        way = track.get(
            "id"
        )

        raw_nodes += len(nodes)

        for i in range(
            len(nodes) - 1
        ):

            node_a = nodes[i]
            node_b = nodes[i + 1]

            point_a = geometry[i]
            point_b = geometry[i + 1]

            distance = point_distance(
                point_a,
                point_b
            )

            if node_a not in graph:

                graph[node_a] = {

                    "point": point_a,

                    "edges": []

                }

            if node_b not in graph:

                graph[node_b] = {

                    "point": point_b,

                    "edges": []

                }

            #
            # A -> B
            #
            key_ab = (
                node_a,
                node_b,
                way
            )

            if key_ab not in edge_cache:

                graph[node_a]["edges"].append(

                    {

                        "node": node_b,

                        "distance": distance,

                        "way": way,

                        "tags": tags

                    }

                )

                edge_cache.add(
                    key_ab
                )

            #
            # B -> A
            #
            key_ba = (
                node_b,
                node_a,
                way
            )

            if key_ba not in edge_cache:

                graph[node_b]["edges"].append(

                    {

                        "node": node_a,

                        "distance": distance,

                        "way": way,

                        "tags": tags

                    }

                )

                edge_cache.add(
                    key_ba
                )

    print(
        "使用way:",
        used_ways
    )

    print(
        "原始节点:",
        raw_nodes
    )

    print(
        "最终节点:",
        len(graph)
    )

    return graph