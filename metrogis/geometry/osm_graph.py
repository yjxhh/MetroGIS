"""
MetroGIS OSM Graph V5.2

OSM Way -> Graph

功能:

1. 节点拓扑
2. WGS84 椭球测地距离
3. 保存 Way metadata
4. railway 过滤
5. route 过滤
6. name 过滤
7. 去除重复 Edge
8. Edge 保存完整 metadata
9. 保存节点所属 Way
10. 保存节点所属线路
11. 自动建立换乘 Edge
12. 换乘距离限制
13. 防止同线路错误建立换乘
14. 支持 Relation / Way 驱动线路 Graph

距离模型:

    WGS84 Geod.inv()

注意:

Web Mercator 仅用于空间网格索引。
真正的距离计算全部使用 WGS84 Geod。

重要:

本文件不能 import 自己。
不要加入:

    from metrogis.geometry.osm_graph import ...
"""

from math import sqrt

from pyproj import Geod
from pyproj import Transformer


#
# --------------------------------------------------
# WGS84 椭球
# --------------------------------------------------
#

geod = Geod(
    ellps="WGS84"
)


#
# --------------------------------------------------
# Web Mercator
# --------------------------------------------------
#
# 仅用于空间网格索引。
# 不用于最终距离计算。
#

transformer = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:3857",
    always_xy=True
)


#
# --------------------------------------------------
# 默认换乘最大距离
# --------------------------------------------------
#

TRANSFER_MAX_DISTANCE = 15.0


#
# --------------------------------------------------
# 经纬度 -> 空间索引坐标
# --------------------------------------------------
#

def point_to_meter(
    point
):
    """
    经纬度转换为 Web Mercator 坐标。

    注意:

    这里只用于空间索引。

    不作为实际距离。
    """

    if point is None:

        return None

    try:

        return transformer.transform(
            float(point[0]),
            float(point[1])
        )

    except (
        TypeError,
        ValueError,
        IndexError
    ):

        return None


#
# --------------------------------------------------
# WGS84 两点距离
# --------------------------------------------------
#

def point_distance(
    a,
    b
):
    """
    使用 WGS84 椭球计算两点真实地表距离。

    参数:

        a = [lng, lat]
        b = [lng, lat]

    返回:

        米
    """

    if a is None or b is None:

        return float("inf")

    try:

        lon1 = float(
            a[0]
        )

        lat1 = float(
            a[1]
        )

        lon2 = float(
            b[0]
        )

        lat2 = float(
            b[1]
        )

    except (
        TypeError,
        ValueError,
        IndexError
    ):

        return float("inf")

    try:

        _, _, distance = geod.inv(
            lon1,
            lat1,
            lon2,
            lat2
        )

    except Exception:

        return float("inf")

    return abs(
        float(distance)
    )


#
# --------------------------------------------------
# 获取线路标识
# --------------------------------------------------
#

def get_line_id(
    tags,
    way=None
):
    """
    从 OSM tags 获取线路标识。

    优先级:

        name
        ref
        operator + route
        route

    返回:

        str | None
    """

    if not tags:

        return None

    #
    # name
    #

    name = tags.get(
        "name"
    )

    if name:

        value = str(
            name
        ).strip()

        if value:

            return value

    #
    # ref
    #

    ref = tags.get(
        "ref"
    )

    if ref:

        value = str(
            ref
        ).strip()

        if value:

            return value

    #
    # operator + route
    #

    operator = tags.get(
        "operator"
    )

    route = tags.get(
        "route"
    )

    if operator and route:

        return (
            f"{operator}:"
            f"{route}"
        )

    #
    # route
    #

    if route:

        value = str(
            route
        ).strip()

        if value:

            return value

    return None


#
# --------------------------------------------------
# Way 过滤
# --------------------------------------------------
#

def check_filter(
    track,
    railway_filter=None,
    route_filter=None,
    name_filter=None
):
    """
    判断 Way 是否保留。
    """

    tags = track.get(
        "tags",
        {}
    )

    #
    # railway
    #

    if railway_filter:

        railway = tags.get(
            "railway"
        )

        if railway != railway_filter:

            return False

    #
    # route
    #

    if route_filter:

        route = tags.get(
            "route"
        )

        if route != route_filter:

            return False

    #
    # name
    #

    if name_filter:

        name = tags.get(
            "name",
            ""
        )

        if name_filter not in name:

            return False

    return True


#
# --------------------------------------------------
# 创建 Node
# --------------------------------------------------
#

def create_graph_node(
    point
):
    """
    创建 Graph Node。
    """

    return {

        "point":
            point,

        "edges":
            [],

        "ways":
            set(),

        "lines":
            set(),

        "line_ways":
            {}

    }


#
# --------------------------------------------------
# 添加普通轨道 Edge
# --------------------------------------------------
#

def add_track_edge(
    graph,
    edge_cache,
    node_a,
    node_b,
    distance,
    way,
    tags
):
    """
    添加普通轨道双向 Edge。
    """

    #
    # A -> B
    #

    key_ab = (
        node_a,
        node_b,
        way
    )

    if key_ab not in edge_cache:

        graph[node_a][
            "edges"
        ].append(
            {
                "node":
                    node_b,

                "distance":
                    distance,

                "way":
                    way,

                "tags":
                    tags,

                "type":
                    "track"
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

        graph[node_b][
            "edges"
        ].append(
            {
                "node":
                    node_a,

                "distance":
                    distance,

                "way":
                    way,

                "tags":
                    tags,

                "type":
                    "track"
            }
        )

        edge_cache.add(
            key_ba
        )


#
# --------------------------------------------------
# 添加换乘 Edge
# --------------------------------------------------
#

def add_transfer_edge(
    graph,
    transfer_cache,
    node_a,
    node_b,
    distance,
    line_a,
    line_b,
    way_a=None,
    way_b=None
):
    """
    添加换乘双向 Edge。

    distance 使用 WGS84 测地距离。
    """

    #
    # 节点对标准化
    #

    pair = tuple(
        sorted(
            (
                node_a,
                node_b
            )
        )
    )

    if pair in transfer_cache:

        return False

    transfer_cache.add(
        pair
    )

    #
    # A -> B
    #

    graph[node_a][
        "edges"
    ].append(
        {
            "node":
                node_b,

            "distance":
                distance,

            "way":
                None,

            "tags":
                {
                    "railway":
                        "transfer"
                },

            "type":
                "transfer",

            "from_line":
                line_a,

            "to_line":
                line_b,

            "from_way":
                way_a,

            "to_way":
                way_b
        }
    )

    #
    # B -> A
    #

    graph[node_b][
        "edges"
    ].append(
        {
            "node":
                node_a,

            "distance":
                distance,

            "way":
                None,

            "tags":
                {
                    "railway":
                        "transfer"
                },

            "type":
                "transfer",

            "from_line":
                line_b,

            "to_line":
                line_a,

            "from_way":
                way_b,

            "to_way":
                way_a
        }
    )

    return True


#
# --------------------------------------------------
# 建立 OSM Graph
# --------------------------------------------------
#

def build_osm_graph(
    tracks,
    railway_filter=None,
    route_filter=None,
    name_filter=None,
    transfer_max_distance=TRANSFER_MAX_DISTANCE
):
    """
    构建 OSM Graph。

    graph:

    {
        node_id:
        {
            "point": [lng, lat],

            "edges":
            [
                {
                    "node": node_id,
                    "distance": metres,
                    "way": way_id,
                    "tags": {...},
                    "type": "track"
                },

                {
                    "node": node_id,
                    "distance": metres,
                    "way": None,
                    "tags": {...},
                    "type": "transfer",
                    "from_line": ...,
                    "to_line": ...
                }
            ],

            "ways": set(),

            "lines": set(),

            "line_ways": {}
        }
    }

    说明:

    - 普通轨道 Edge 双向
    - 换乘 Edge 双向
    - 距离统一 WGS84
    - transfer_max_distance <= 0 时不建立换乘
    """

    print(
        "构建OSM Graph..."
    )

    graph = {}

    raw_nodes = 0

    used_ways = 0

    #
    # 普通 Edge 去重
    #

    edge_cache = set()

    #
    # 换乘 Edge 去重
    #

    transfer_cache = set()

    #
    # 保存 Way 信息
    #

    way_info = {}

    #
    # --------------------------------------------------
    # 第一阶段:
    # 构建轨道拓扑
    # --------------------------------------------------
    #

    for track in tracks:

        #
        # 过滤
        #

        if not check_filter(
            track,
            railway_filter=railway_filter,
            route_filter=route_filter,
            name_filter=name_filter
        ):

            continue

        #
        # 节点
        #

        nodes = track.get(
            "nodes",
            []
        )

        #
        # 几何
        #

        geometry = track.get(
            "geometry",
            []
        )

        #
        # 数据完整性
        #

        if len(nodes) < 2:

            continue

        if len(nodes) != len(
            geometry
        ):

            continue

        used_ways += 1

        #
        # tags
        #

        tags = dict(
            track.get(
                "tags",
                {}
            )
        )

        #
        # Way ID
        #

        way = track.get(
            "id"
        )

        #
        # 线路标识
        #

        line_id = get_line_id(
            tags,
            way
        )

        #
        # 保存 Way 信息
        #

        way_info[
            way
        ] = {
            "line":
                line_id,

            "tags":
                tags
        }

        #
        # 节点统计
        #

        raw_nodes += len(
            nodes
        )

        #
        # --------------------------------------------------
        # 注册节点
        # --------------------------------------------------
        #

        for i in range(
            len(nodes)
        ):

            node_id = nodes[i]

            point = geometry[i]

            if node_id not in graph:

                graph[node_id] = create_graph_node(
                    point
                )

            #
            # 如果已有节点但当前 Geometry
            # 更完整，则更新 point。
            #

            if (
                not graph[node_id].get(
                    "point"
                )
                and point
            ):

                graph[node_id][
                    "point"
                ] = point

            #
            # Way
            #

            graph[node_id][
                "ways"
            ].add(
                way
            )

            #
            # Line
            #

            if line_id:

                graph[node_id][
                    "lines"
                ].add(
                    line_id
                )

                if line_id not in graph[node_id][
                    "line_ways"
                ]:

                    graph[node_id][
                        "line_ways"
                    ][line_id] = set()

                graph[node_id][
                    "line_ways"
                ][line_id].add(
                    way
                )

        #
        # --------------------------------------------------
        # 构建 Way 相邻 Edge
        # --------------------------------------------------
        #

        for i in range(
            len(nodes) - 1
        ):

            node_a = nodes[i]

            node_b = nodes[i + 1]

            point_a = geometry[i]

            point_b = geometry[i + 1]

            #
            # WGS84 真实距离
            #

            distance = point_distance(
                point_a,
                point_b
            )

            #
            # 无效距离跳过
            #

            if (
                distance == float("inf")
            ):

                continue

            add_track_edge(
                graph,
                edge_cache,
                node_a,
                node_b,
                distance,
                way,
                tags
            )

    #
    # --------------------------------------------------
    # 基础统计
    # --------------------------------------------------
    #

    print(
        f"使用way: {used_ways}"
    )

    print(
        f"原始节点: {raw_nodes}"
    )

    print(
        f"线路节点: {len(graph)}"
    )

    #
    # --------------------------------------------------
    # 不需要换乘
    # --------------------------------------------------
    #

    if (
        transfer_max_distance is None
        or
        transfer_max_distance <= 0
    ):

        print(
            "建立换乘连接..."
        )

        print(
            "换乘连接: 0"
        )

        return graph

    #
    # --------------------------------------------------
    # 第二阶段:
    # 建立空间索引
    # --------------------------------------------------
    #

    print(
        "建立换乘连接..."
    )

    meter_points = {}

    for node_id, data in graph.items():

        point = data.get(
            "point"
        )

        meter = point_to_meter(
            point
        )

        if meter is not None:

            meter_points[
                node_id
            ] = meter

    #
    # 空间网格大小
    #

    cell_size = float(
        transfer_max_distance
    )

    if cell_size <= 0:

        print(
            "换乘连接: 0"
        )

        return graph

    grid = {}

    #
    # 建立网格
    #

    for node_id, point in meter_points.items():

        x, y = point

        cell_x = int(
            x // cell_size
        )

        cell_y = int(
            y // cell_size
        )

        key = (
            cell_x,
            cell_y
        )

        if key not in grid:

            grid[key] = []

        grid[key].append(
            node_id
        )

    #
    # --------------------------------------------------
    # 查找换乘
    # --------------------------------------------------
    #

    transfer_pairs = 0

    for node_a, data_a in graph.items():

        if node_a not in meter_points:

            continue

        point_a_meter = meter_points[
            node_a
        ]

        x_a, y_a = point_a_meter

        cell_x = int(
            x_a // cell_size
        )

        cell_y = int(
            y_a // cell_size
        )

        #
        # 当前节点线路
        #

        lines_a = data_a.get(
            "lines",
            set()
        )

        if not lines_a:

            continue

        #
        # 当前节点 Way
        #

        ways_a = data_a.get(
            "ways",
            set()
        )

        #
        # 9 个网格
        #

        for dx in (
            -1,
            0,
            1
        ):

            for dy in (
                -1,
                0,
                1
            ):

                key = (
                    cell_x + dx,
                    cell_y + dy
                )

                candidates = grid.get(
                    key,
                    []
                )

                for node_b in candidates:

                    #
                    # 自身
                    #

                    if node_a == node_b:

                        continue

                    #
                    # 一对节点只处理一次
                    #

                    if node_a > node_b:

                        continue

                    data_b = graph[
                        node_b
                    ]

                    #
                    # 线路
                    #

                    lines_b = data_b.get(
                        "lines",
                        set()
                    )

                    if not lines_b:

                        continue

                    #
                    # 同线路不建立换乘
                    #

                    if lines_a.intersection(
                        lines_b
                    ):

                        continue

                    #
                    # Way
                    #

                    ways_b = data_b.get(
                        "ways",
                        set()
                    )

                    #
                    # 共享 Way 不建立换乘
                    #

                    if ways_a.intersection(
                        ways_b
                    ):

                        continue

                    #
                    # --------------------------------------------------
                    # WGS84 精确距离
                    # --------------------------------------------------
                    #

                    point_b = data_b.get(
                        "point"
                    )

                    distance = point_distance(
                        data_a.get(
                            "point"
                        ),
                        point_b
                    )

                    if (
                        distance
                        ==
                        float("inf")
                    ):

                        continue

                    if (
                        distance
                        >
                        transfer_max_distance
                    ):

                        continue

                    #
                    # --------------------------------------------------
                    # 找真正不同的线路
                    # --------------------------------------------------
                    #

                    line_a = None

                    line_b = None

                    for candidate_a in lines_a:

                        for candidate_b in lines_b:

                            if (
                                candidate_a
                                !=
                                candidate_b
                            ):

                                line_a = (
                                    candidate_a
                                )

                                line_b = (
                                    candidate_b
                                )

                                break

                        if line_a is not None:

                            break

                    if (
                        line_a is None
                        or
                        line_b is None
                    ):

                        continue

                    #
                    # --------------------------------------------------
                    # 对应 Way
                    # --------------------------------------------------
                    #

                    ways_for_line_a = (
                        data_a.get(
                            "line_ways",
                            {}
                        ).get(
                            line_a,
                            set()
                        )
                    )

                    ways_for_line_b = (
                        data_b.get(
                            "line_ways",
                            {}
                        ).get(
                            line_b,
                            set()
                        )
                    )

                    way_a = next(
                        iter(
                            ways_for_line_a
                        ),
                        None
                    )

                    way_b = next(
                        iter(
                            ways_for_line_b
                        ),
                        None
                    )

                    #
                    # 添加换乘
                    #

                    added = add_transfer_edge(

                        graph,

                        transfer_cache,

                        node_a,

                        node_b,

                        distance,

                        line_a,

                        line_b,

                        way_a,

                        way_b

                    )

                    if added:

                        transfer_pairs += 1

    #
    # --------------------------------------------------
    # 换乘统计
    # --------------------------------------------------
    #

    print(
        f"换乘连接: {transfer_pairs}"
    )

    #
    # --------------------------------------------------
    # Edge 统计
    # --------------------------------------------------
    #

    edge_count = 0

    track_edge_count = 0

    transfer_edge_count = 0

    for data in graph.values():

        edges = data.get(
            "edges",
            []
        )

        edge_count += len(
            edges
        )

        for edge in edges:

            if edge.get(
                "type"
            ) == "transfer":

                transfer_edge_count += 1

            else:

                track_edge_count += 1

    #
    # --------------------------------------------------
    # 最终统计
    # --------------------------------------------------
    #

    print(
        f"最终节点: {len(graph)}"
    )

    print(
        f"Edge数量: {edge_count}"
    )

    print(
        f"轨道Edge: {track_edge_count}"
    )

    print(
        f"换乘Edge: {transfer_edge_count}"
    )

    return graph