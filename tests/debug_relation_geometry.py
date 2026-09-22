"""
MetroGIS Relation Geometry Diagnostic

检查:

1. Relation 数量
2. Relation stop 顺序
3. Relation way member 顺序
4. 每个 Way 的真实 WGS84 长度
5. Way 首尾节点
6. Way 是否能够按照 Relation 顺序连续连接
7. Relation 总几何长度

目的:

确认线路长度异常究竟来自:

    A. OSM Relation Way 本身

还是:

    B. shortest_path 拓扑选择

还是:

    C. Relation Way 顺序 / 连接关系
"""

from metrogis.api.overpass import (
    get_line_relation_tracks
)

from metrogis.geometry.osm_graph import (
    point_distance
)


BBOX = (
    38.8,
    116.8,
    39.4,
    117.8
)


LINE_NAME = "天津3号线"

LINE_REF = "3"

CITY = "天津"


def geometry_length(
    geometry
):
    """
    WGS84 几何长度。
    """

    total = 0.0

    if not geometry:

        return total

    for i in range(
        len(geometry) - 1
    ):

        total += point_distance(
            geometry[i],
            geometry[i + 1]
        )

    return total


def main():

    print(
        "获取 Relation..."
    )

    result = get_line_relation_tracks(
        LINE_NAME,
        BBOX,
        line_ref=LINE_REF,
        city_name=CITY
    )

    candidates = result.get(
        "candidates",
        []
    )

    if not candidates:

        print(
            "没有找到 Relation"
        )

        return

    print()
    print(
        "=" * 100
    )

    print(
        "Relation 数量:",
        len(candidates)
    )

    print(
        "=" * 100
    )

    for candidate in candidates:

        relation = candidate.get(
            "relation",
            {}
        )

        relation_id = relation.get(
            "id"
        )

        tags = relation.get(
            "tags",
            {}
        )

        stops = candidate.get(
            "stops",
            []
        )

        tracks = candidate.get(
            "tracks",
            []
        )

        print()
        print(
            "#" * 100
        )

        print(
            "RELATION:",
            relation_id
        )

        print(
            "NAME:",
            tags.get(
                "name"
            )
        )

        print(
            "FROM:",
            tags.get(
                "from"
            )
        )

        print(
            "TO:",
            tags.get(
                "to"
            )
        )

        print()
        print(
            "STOP 数量:",
            len(stops)
        )

        print(
            "WAY 数量:",
            len(tracks)
        )

        #
        # --------------------------------------------------
        # Stop
        # --------------------------------------------------
        #

        print()
        print(
            "STOP 顺序:"
        )

        stop_nodes = candidate.get(
            "stop_nodes",
            {}
        )

        for index, stop in enumerate(
            stops
        ):

            node_id = stop.get(
                "node_id"
            )

            node = stop_nodes.get(
                node_id,
                {}
            )

            print(
                f"{index:3d}. "
                f"node={node_id} "
                f"name={node.get('name')} "
                f"lat={node.get('lat')} "
                f"lng={node.get('lng')}"
            )

        #
        # --------------------------------------------------
        # Way
        # --------------------------------------------------
        #

        print()
        print(
            "WAY 顺序:"
        )

        total_length = 0.0

        previous_end_node = None

        continuous_count = 0

        for index, track in enumerate(
            tracks
        ):

            way_id = track.get(
                "id"
            )

            nodes = track.get(
                "nodes",
                []
            )

            geometry = track.get(
                "geometry",
                []
            )

            tags = track.get(
                "tags",
                {}
            )

            length = geometry_length(
                geometry
            )

            total_length += length

            first_node = (
                nodes[0]
                if nodes
                else None
            )

            last_node = (
                nodes[-1]
                if nodes
                else None
            )

            relation_member_index = track.get(
                "relation_member_index"
            )

            relation_role = track.get(
                "relation_role"
            )

            print()

            print(
                f"{index:3d}. "
                f"member={relation_member_index} "
                f"way={way_id}"
            )

            print(
                f"     "
                f"first={first_node} "
                f"last={last_node}"
            )

            print(
                f"     "
                f"nodes={len(nodes)} "
                f"length={length:.2f}m"
            )

            print(
                f"     "
                f"railway={tags.get('railway')} "
                f"service={tags.get('service')} "
                f"name={tags.get('name')}"
            )

            print(
                f"     "
                f"layer={tags.get('layer')} "
                f"bridge={tags.get('bridge')} "
                f"tunnel={tags.get('tunnel')}"
            )

            print(
                f"     "
                f"role={relation_role!r}"
            )

            #
            # 检查相邻 Way 是否直接连接
            #
            if previous_end_node is not None:

                if first_node == previous_end_node:

                    print(
                        "     "
                        "CONNECT: YES"
                    )

                    continuous_count += 1

                elif last_node == previous_end_node:

                    print(
                        "     "
                        "CONNECT: YES (REVERSED)"
                    )

                    continuous_count += 1

                else:

                    print(
                        "     "
                        "CONNECT: NO"
                    )

                    print(
                        "     "
                        f"expected previous end="
                        f"{previous_end_node}"
                    )

            previous_end_node = last_node

        #
        # --------------------------------------------------
        # 总长度
        # --------------------------------------------------
        #

        print()
        print(
            "-" * 100
        )

        print(
            "Relation Way 几何总长度:",
            round(
                total_length,
                2
            ),
            "m"
        )

        print(
            "Way 连续连接:",
            continuous_count,
            "/",
            max(
                0,
                len(tracks) - 1
            )
        )

        #
        # --------------------------------------------------
        # 计算所有 Way 节点集合
        # --------------------------------------------------
        #

        all_nodes = set()

        for track in tracks:

            all_nodes.update(
                track.get(
                    "nodes",
                    []
                )
            )

        print(
            "Way 唯一节点:",
            len(all_nodes)
        )

        #
        # --------------------------------------------------
        # 检查 Stop 是否位于 Way
        # --------------------------------------------------
        #

        print()
        print(
            "Stop -> Way 检查:"
        )

        for index, stop in enumerate(
            stops
        ):

            node_id = stop.get(
                "node_id"
            )

            found_ways = []

            for track in tracks:

                if node_id in track.get(
                    "nodes",
                    []
                ):

                    found_ways.append(
                        track.get(
                            "id"
                        )
                    )

            print(
                f"{index:3d}. "
                f"{node_id} "
                f"-> "
                f"{len(found_ways)} way(s) "
                f"{found_ways}"
            )

        print()
        print(
            "#" * 100
        )


if __name__ == "__main__":

    main()
