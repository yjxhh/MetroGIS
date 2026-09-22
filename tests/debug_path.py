from metrogis.api.track import get_track_geometry
from metrogis.geometry.osm_graph import build_osm_graph
from metrogis.geometry.path_finder import shortest_path


BBOX = (39.05, 117.15, 39.20, 117.25)

stations = [
    (
        "津湾广场",
        (117.2011885, 39.1303448),
        "天津站",
        (117.1924892, 39.0843933),
    ),
    (
        "铁东路",
        (117.2010161, 39.1790552),
        "张兴庄",
        (117.1989, 39.1675),
    ),
]


def nearest_node(graph, point):
    best_node = None
    best_distance = float("inf")

    for node_id, data in graph.items():
        x, y = data["point"]

        dx = x - point[0]
        dy = y - point[1]

        distance = (dx * dx + dy * dy) ** 0.5

        if distance < best_distance:
            best_distance = distance
            best_node = node_id

    return best_node, best_distance


def get_edge(graph, node_a, node_b):
    """
    找到实际经过的 A -> B Edge
    """

    for edge in graph[node_a]["edges"]:

        if edge.get("node") == node_b:

            return edge

    return None


def edge_line_name(edge):
    """
    获取普通轨道 Edge 的线路名称
    """

    tags = edge.get(
        "tags",
        {}
    )

    return (
        tags.get("name")
        or tags.get("ref")
        or tags.get("operator")
        or "UNKNOWN"
    )


def main():

    print("获取轨迹...")

    tracks = get_track_geometry(
        BBOX
    )

    print(
        f"轨迹数量: {len(tracks)}"
    )

    print("构建 Graph...")

    graph = build_osm_graph(
        tracks
    )

    print(
        f"Graph 节点: {len(graph)}"
    )

    for (
        start_name,
        start_point,
        end_name,
        end_point
    ) in stations:

        print()
        print("=" * 70)
        print(
            f"{start_name} -> {end_name}"
        )

        start_node, start_distance = nearest_node(
            graph,
            start_point
        )

        end_node, end_distance = nearest_node(
            graph,
            end_point
        )

        print(
            f"start: {start_node} "
            f"距离车站 {start_distance * 111000:.2f}m"
        )

        print(
            f"end:   {end_node} "
            f"距离车站 {end_distance * 111000:.2f}m"
        )

        if start_node is None or end_node is None:

            print("没有找到最近节点")

            continue

        path = shortest_path(
            graph,
            start_node,
            end_node
        )

        if not path:

            print("path nodes: 0")
            print("没有找到路径")

            continue

        print(
            f"path nodes: {len(path)}"
        )

        #
        # 实际经过的换乘 Edge
        #
        actual_transfers = []

        #
        # 实际经过的线路
        #
        line_sequence = []

        #
        # 统计普通/换乘 Edge
        #
        track_edges = 0
        transfer_edges = 0

        #
        # 逐条检查路径上的 Edge
        #
        for i in range(
            len(path) - 1
        ):

            node_a = path[i]
            node_b = path[i + 1]

            edge = get_edge(
                graph,
                node_a,
                node_b
            )

            if edge is None:

                print(
                    f"WARNING: 找不到 Edge "
                    f"{node_a} -> {node_b}"
                )

                continue

            edge_type = edge.get(
                "type",
                "track"
            )

            if edge_type == "transfer":

                transfer_edges += 1

                actual_transfers.append(
                    (
                        node_a,
                        node_b,
                        edge
                    )
                )

                from_line = edge.get(
                    "from_line"
                )

                to_line = edge.get(
                    "to_line"
                )

                print()
                print(
                    ">>> 实际经过换乘"
                )

                print(
                    f"    node: {node_a} -> {node_b}"
                )

                print(
                    f"    distance: "
                    f"{edge.get('distance', 0):.2f}m"
                )

                print(
                    f"    line: "
                    f"{from_line} -> {to_line}"
                )

                print(
                    f"    way: "
                    f"{edge.get('from_way')} "
                    f"-> "
                    f"{edge.get('to_way')}"
                )

                #
                # 线路序列
                #
                if not line_sequence:

                    if from_line:
                        line_sequence.append(
                            from_line
                        )

                if to_line:

                    if (
                        not line_sequence
                        or line_sequence[-1] != to_line
                    ):

                        line_sequence.append(
                            to_line
                        )

            else:

                track_edges += 1

                line_name = edge_line_name(
                    edge
                )

                if not line_sequence:

                    line_sequence.append(
                        line_name
                    )

                elif line_sequence[-1] != line_name:

                    line_sequence.append(
                        line_name
                    )

        print()
        print("-" * 70)

        print(
            f"实际轨道 Edge: {track_edges}"
        )

        print(
            f"实际换乘 Edge: {transfer_edges}"
        )

        print(
            f"线路序列:"
        )

        for i, line in enumerate(
            line_sequence,
            start=1
        ):

            print(
                f"  {i}. {line}"
            )

        print()

        #
        # 打印所有实际换乘
        #
        if actual_transfers:

            print(
                "换乘明细:"
            )

            for (
                node_a,
                node_b,
                edge
            ) in actual_transfers:

                print(
                    f"  "
                    f"{edge.get('from_line')}"
                    f" -> "
                    f"{edge.get('to_line')}"
                    f" | "
                    f"{edge.get('distance', 0):.2f}m"
                )

        else:

            print(
                "本次路径没有实际经过换乘 Edge"
            )

        #
        # 输出完整节点路径前 30 个
        #
        print()

        print(
            "path:"
        )

        print(
            path[:30]
        )

        if len(path) > 30:

            print("...")


if __name__ == "__main__":

    main()