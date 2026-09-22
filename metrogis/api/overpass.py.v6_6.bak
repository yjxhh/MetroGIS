"""
MetroGIS Overpass API V4

核心功能:

1. Overpass 请求
2. 线路 Relation 查询
3. 同线路方向 Relation 分离
4. Relation stop 顺序提取
5. Relation Way 成员提取
6. Relation -> Way Geometry
7. 线路拓扑数据发现

核心原则:

线路身份:
    OSM route relation

线路站序:
    relation member role=stop

线路几何:
    relation member type=way

不再把不同方向 Relation 的 Way 混合。
"""

import re
import time

import requests


#
# --------------------------------------------------
# Overpass Server
# --------------------------------------------------
#

OVERPASS_SERVERS = [

    "https://overpass-api.de/api/interpreter",

    "https://overpass.kumi.systems/api/interpreter",

    "https://overpass.private.coffee/api/interpreter"

]


#
# --------------------------------------------------
# HTTP Header
# --------------------------------------------------
#

HEADERS = {
    "User-Agent":
        "MetroGIS/4.0 "
        "(national metro GIS project)"
}


#
# --------------------------------------------------
# 请求 Overpass
# --------------------------------------------------
#

def query_overpass(
    query,
    retry=3
):
    """
    请求 Overpass API。

    自动:

    1. 多服务器
    2. 重试
    3. 超时
    """

    last_error = None

    for server in OVERPASS_SERVERS:

        for attempt in range(
            retry
        ):

            try:

                print(
                    "Query Overpass:",
                    server
                )

                response = requests.post(
                    server,
                    data=query.encode(
                        "utf-8"
                    ),
                    headers=HEADERS,
                    timeout=180
                )

                response.raise_for_status()

                return response.json()

            except Exception as exc:

                last_error = exc

                print(
                    f"failed "
                    f"{attempt + 1}/{retry}:",
                    exc
                )

                if attempt < retry - 1:

                    time.sleep(
                        2
                    )

    raise RuntimeError(
        last_error
    )


#
# --------------------------------------------------
# 文本标准化
# --------------------------------------------------
#

def normalize_text(
    value
):
    """
    标准化文本。
    """

    if value is None:

        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace(
            " ",
            ""
        )
        .replace(
            "　",
            ""
        )
    )


#
# --------------------------------------------------
# Relation 名称标准化
# --------------------------------------------------
#

def normalize_relation_name(
    name
):
    """
    去除方向后缀。

    例如:

        地铁3号线:南站→小淀
        地铁3号线:小淀→南站

    保留基础线路语义。
    """

    value = normalize_text(
        name
    )

    if not value:

        return ""

    #
    # 去掉最后 :xxx
    #
    value = re.sub(
        r":[^:]+$",
        "",
        value
    )

    return value


#
# --------------------------------------------------
# ref 标准化
# --------------------------------------------------
#

def normalize_ref(
    ref
):
    """
    获取数字 ref。

    例如:

        3
        03
        3号线

    -> 3
    """

    if ref is None:

        return ""

    value = normalize_text(
        ref
    )

    match = re.search(
        r"\d+",
        value
    )

    if match:

        return str(
            int(
                match.group(
                    0
                )
            )
        )

    return value


#
# --------------------------------------------------
# Relation 评分
# --------------------------------------------------
#

def score_relation(
    relation,
    line_name=None,
    line_ref=None,
    city_name=None
):
    """
    计算 Relation 与目标线路的匹配程度。
    """

    tags = relation.get(
        "tags",
        {}
    )

    name = tags.get(
        "name",
        ""
    )

    ref = tags.get(
        "ref",
        ""
    )

    network = tags.get(
        "network",
        ""
    )

    operator = tags.get(
        "operator",
        ""
    )

    route = tags.get(
        "route",
        ""
    )

    score = 0

    #
    # 路线类型
    #
    if normalize_text(
        route
    ) in {
        "subway",
        "light_rail",
        "rail"
    }:

        score += 20

    #
    # ref
    #
    target_ref = normalize_ref(
        line_ref
    )

    osm_ref = normalize_ref(
        ref
    )

    if (
        target_ref
        and
        osm_ref
        and
        target_ref == osm_ref
    ):

        score += 100

    #
    # name
    #
    target_name = normalize_relation_name(
        line_name
    )

    relation_name = normalize_relation_name(
        name
    )

    if (
        target_name
        and
        relation_name
    ):

        if (
            target_name == relation_name
        ):

            score += 100

        elif (
            target_name in relation_name
            or
            relation_name in target_name
        ):

            score += 50

    #
    # 城市
    #
    if city_name:

        city = normalize_text(
            city_name
        )

        if city:

            if city in normalize_text(
                network
            ):

                score += 15

            if city in normalize_text(
                operator
            ):

                score += 5

    return score


#
# --------------------------------------------------
# 查询目标线路 Relation
# --------------------------------------------------
#

def build_line_relation_query(
    line_name,
    bbox,
    line_ref=None
):
    """
    查询目标线路所有 Relation。

    不使用方向后缀。

    例如:

        天津3号线

    可以找到:

        地铁3号线:南站→小淀
        地铁3号线:小淀→南站
    """

    south, west, north, east = bbox

    target_name = normalize_relation_name(
        line_name
    )

    pattern = re.escape(
        target_name
    )

    clauses = []

    for route in (
        "subway",
        "light_rail",
        "rail"
    ):

        clauses.append(
            f"""
            relation
            [
                route="{route}"
            ]
            [
                name~"{pattern}",i
            ]
            ({south},{west},{north},{east});
            """
        )

    #
    # ref 查询
    #
    ref_value = normalize_ref(
        line_ref
    )

    if ref_value:

        for route in (
            "subway",
            "light_rail",
            "rail"
        ):

            clauses.append(
                f"""
                relation
                [
                    route="{route}"
                ]
                [
                    ref="{ref_value}"
                ]
                ({south},{west},{north},{east});
                """
            )

    return f"""
[out:json][timeout:180];

(
    {"".join(clauses)}
);

out body;
"""


#
# --------------------------------------------------
# 查找线路 Relation
# --------------------------------------------------
#

def find_line_relations(
    line_name,
    bbox,
    line_ref=None,
    city_name=None
):
    """
    找到目标线路的全部 Relation。

    不合并方向。

    返回:

        relation list
    """

    query = build_line_relation_query(
        line_name,
        bbox,
        line_ref=line_ref
    )

    data = query_overpass(
        query
    )

    relations = []

    seen = set()

    for element in data.get(
        "elements",
        []
    ):

        if element.get(
            "type"
        ) != "relation":

            continue

        relation_id = element.get(
            "id"
        )

        if relation_id in seen:

            continue

        seen.add(
            relation_id
        )

        score = score_relation(
            element,
            line_name=line_name,
            line_ref=line_ref,
            city_name=city_name
        )

        if score < 50:

            continue

        relation = dict(
            element
        )

        relation[
            "_score"
        ] = score

        relations.append(
            relation
        )

    relations.sort(
        key=lambda item:
        (
            -item.get(
                "_score",
                0
            ),
            item.get(
                "id",
                0
            )
        )
    )

    return relations


#
# --------------------------------------------------
# Relation Stop 提取
# --------------------------------------------------
#

def extract_relation_stops(
    relation
):
    """
    提取 Relation 中 role=stop 的 node。

    保持 Relation 原始顺序。

    返回:

    [
        {
            "node_id": ...,
            "role": "stop",
            "index": ...
        }
    ]
    """

    stops = []

    members = relation.get(
        "members",
        []
    )

    for index, member in enumerate(
        members
    ):

        if member.get(
            "type"
        ) != "node":

            continue

        role = member.get(
            "role",
            ""
        )

        if role != "stop":

            continue

        node_id = member.get(
            "ref"
        )

        if node_id is None:

            continue

        stops.append(
            {
                "node_id":
                    node_id,

                "role":
                    role,

                "index":
                    index
            }
        )

    return stops


#
# --------------------------------------------------
# 查询 Stop Node
# --------------------------------------------------
#

def get_relation_stop_nodes(
    stop_ids
):
    """
    查询 Relation stop node 的坐标和 tags。
    """

    if not stop_ids:

        return {}

    ids = ",".join(
        str(node_id)
        for node_id in stop_ids
    )

    query = f"""
[out:json][timeout:180];

node(
    id:{ids}
);

out body;
"""

    data = query_overpass(
        query
    )

    result = {}

    for element in data.get(
        "elements",
        []
    ):

        node_id = element.get(
            "id"
        )

        if node_id is None:

            continue

        result[node_id] = {

            "id":
                node_id,

            "lat":
                element.get(
                    "lat"
                ),

            "lng":
                element.get(
                    "lon"
                ),

            "name":
                element.get(
                    "tags",
                    {}
                ).get(
                    "name"
                ),

            "tags":
                dict(
                    element.get(
                        "tags",
                        {}
                    )
                )

        }

    return result


#
# --------------------------------------------------
# 查询 Relation Way
# --------------------------------------------------
#

def build_relation_way_query(
    relation_ids
):
    """
    查询多个 Relation 的 Way。
    """

    ids = ",".join(
        str(
            relation_id
        )
        for relation_id in relation_ids
    )

    return f"""
[out:json][timeout:180];

(
    relation(
        id:{ids}
    );

    way(r);
);

out body geom;
"""


#
# --------------------------------------------------
# Way 与 Relation 建立映射
# --------------------------------------------------
#

def _relation_way_members(
    relation
):
    """
    获取一个 Relation 的直接 Way 成员。
    """

    result = []

    for index, member in enumerate(
        relation.get(
            "members",
            []
        )
    ):

        if member.get(
            "type"
        ) != "way":

            continue

        way_id = member.get(
            "ref"
        )

        if way_id is None:

            continue

        result.append(
            {
                "way_id":
                    way_id,

                "index":
                    index,

                "role":
                    member.get(
                        "role",
                        ""
                    )
            }
        )

    return result


#
# --------------------------------------------------
# 线路 Relation + Way 数据
# --------------------------------------------------
#

def get_line_relation_tracks(
    line_name,
    bbox,
    line_ref=None,
    city_name=None
):
    """
    获取目标线路的 Relation 数据。

    重要:

    每一个方向 Relation 单独保存。

    返回:

    {
        "relations": [...],

        "candidates": [
            {
                "relation": {...},

                "stops": [...],

                "stop_nodes": {...},

                "tracks": [...],

                "relation_way_ids": set()
            }
        ]
    }
    """

    print(
        "搜索线路 OSM Relation..."
    )

    relations = find_line_relations(
        line_name,
        bbox,
        line_ref=line_ref,
        city_name=city_name
    )

    if not relations:

        print(
            "未找到目标线路 Relation"
        )

        return {
            "relations": [],

            "candidates": []
        }

    print(
        "找到 Relation:",
        len(relations)
    )

    for relation in relations:

        tags = relation.get(
            "tags",
            {}
        )

        print(
            " Relation:",
            relation.get(
                "id"
            ),
            "| name=",
            tags.get(
                "name"
            ),
            "| ref=",
            tags.get(
                "ref"
            ),
            "| score=",
            relation.get(
                "_score"
            )
        )

    #
    # --------------------------------------------------
    # 收集全部 Stop
    # --------------------------------------------------
    #

    all_stop_ids = set()

    relation_stop_map = {}

    for relation in relations:

        relation_id = relation.get(
            "id"
        )

        stops = extract_relation_stops(
            relation
        )

        relation_stop_map[
            relation_id
        ] = stops

        for stop in stops:

            all_stop_ids.add(
                stop[
                    "node_id"
                ]
            )

    print(
        "Relation Stop Node:",
        len(
            all_stop_ids
        )
    )

    #
    # 查询 Stop Node
    #
    stop_nodes = get_relation_stop_nodes(
        all_stop_ids
    )

    #
    # --------------------------------------------------
    # 查询全部 Way
    # --------------------------------------------------
    #

    relation_ids = [
        relation.get(
            "id"
        )
        for relation in relations
    ]

    query = build_relation_way_query(
        relation_ids
    )

    data = query_overpass(
        query
    )

    way_tracks = {}

    for element in data.get(
        "elements",
        []
    ):

        if element.get(
            "type"
        ) != "way":

            continue

        way_id = element.get(
            "id"
        )

        if way_id is None:

            continue

        nodes = element.get(
            "nodes",
            []
        )

        geometry_raw = element.get(
            "geometry",
            []
        )

        geometry = []

        for point in geometry_raw:

            lon = point.get(
                "lon"
            )

            lat = point.get(
                "lat"
            )

            if lon is None or lat is None:

                continue

            geometry.append(
                [
                    float(lon),
                    float(lat)
                ]
            )

        if (
            len(nodes) < 2
            or
            len(nodes) != len(
                geometry
            )
        ):

            continue

        way_tracks[
            way_id
        ] = {

            "id":
                way_id,

            "nodes":
                nodes,

            "geometry":
                geometry,

            "tags":
                dict(
                    element.get(
                        "tags",
                        {}
                    )
                )

        }

    #
    # --------------------------------------------------
    # 为每一个 Relation 分配独立 Way
    # --------------------------------------------------
    #

    candidates = []

    for relation in relations:

        relation_id = relation.get(
            "id"
        )

        members = _relation_way_members(
            relation
        )

        tracks = []

        seen_way_ids = set()

        relation_way_ids = set()

        for member in members:

            way_id = member[
                "way_id"
            ]

            relation_way_ids.add(
                way_id
            )

            if way_id in seen_way_ids:

                continue

            seen_way_ids.add(
                way_id
            )

            track = way_tracks.get(
                way_id
            )

            if track is None:

                continue

            track_copy = dict(
                track
            )

            track_copy[
                "relation_id"
            ] = relation_id

            track_copy[
                "relation_member_index"
            ] = member[
                "index"
            ]

            track_copy[
                "relation_role"
            ] = member[
                "role"
            ]

            tracks.append(
                track_copy
            )

        stops = relation_stop_map.get(
            relation_id,
            []
        )

        candidate = {

            "relation":
                relation,

            "stops":
                stops,

            "stop_nodes":
                stop_nodes,

            "tracks":
                tracks,

            "relation_way_ids":
                relation_way_ids

        }

        candidates.append(
            candidate
        )

        print()
        print(
            "Relation候选:",
            relation_id
        )

        print(
            "  Stop:",
            len(
                stops
            )
        )

        print(
            "  Way:",
            len(
                relation_way_ids
            )
        )

        print(
            "  Geometry Way:",
            len(
                tracks
            )
        )

    #
    # 保留旧字段，
    # 兼容其它代码。
    #
    all_tracks = []

    all_way_ids = set()

    seen = set()

    for candidate in candidates:

        all_way_ids.update(
            candidate[
                "relation_way_ids"
            ]
        )

        for track in candidate[
            "tracks"
        ]:

            way_id = track.get(
                "id"
            )

            if way_id in seen:

                continue

            seen.add(
                way_id
            )

            all_tracks.append(
                track
            )

    return {

        "relations":
            relations,

        "candidates":
            candidates,

        "tracks":
            all_tracks,

        "relation_way_ids":
            all_way_ids

    }


#
# --------------------------------------------------
# 旧版接口兼容
# --------------------------------------------------
#

def build_query(
    line_name,
    bbox
):
    """
    兼容旧代码。
    """

    return build_line_relation_query(
        line_name,
        bbox
    )


def search_metro_line(
    line_name,
    bbox
):
    """
    兼容旧代码。
    """

    query = build_line_relation_query(
        line_name,
        bbox
    )

    return query_overpass(
        query
    )


#
# --------------------------------------------------
# 列出城市线路
# --------------------------------------------------
#

def list_metro_lines(
    city
):
    """
    列出城市线路。

    同一线路多个方向 Relation 合并成一条线路。
    """

    city_name = str(
        city
    ).strip()

    query = f"""
[out:json][timeout:180];

relation
[
    route~"^(subway|light_rail|rail)$"
]
[
    name
]
({-90},{-180},{90},{180});

out body;
"""

    data = query_overpass(
        query
    )

    groups = {}

    city_text = normalize_text(
        city_name
    )

    for element in data.get(
        "elements",
        []
    ):

        if element.get(
            "type"
        ) != "relation":

            continue

        tags = element.get(
            "tags",
            {}
        )

        name = tags.get(
            "name"
        )

        if not name:

            continue

        network = tags.get(
            "network"
        )

        ref = tags.get(
            "ref"
        )

        route = tags.get(
            "route"
        )

        searchable = (

            normalize_text(
                name
            )

            +

            normalize_text(
                network
            )

            +

            normalize_text(
                tags.get(
                    "operator"
                )
            )

        )

        if (
            city_text
            and
            city_text not in searchable
        ):

            continue

        base_name = normalize_relation_name(
            name
        )

        if network and ref:

            key = (
                normalize_text(
                    network
                ),
                normalize_ref(
                    ref
                )
            )

        elif network:

            key = (
                normalize_text(
                    network
                ),
                base_name
            )

        else:

            key = (
                "",
                base_name
            )

        group = groups.setdefault(
            key,
            {
                "ref":
                    ref,

                "name":
                    base_name,

                "network":
                    network,

                "route":
                    route,

                "relations":
                    []
            }
        )

        group[
            "relations"
        ].append(
            element
        )

    result = []

    for key, group in groups.items():

        refs = []

        directions = []

        relation_ids = []

        from_value = None

        to_value = None

        for relation in group[
            "relations"
        ]:

            relation_id = relation.get(
                "id"
            )

            relation_ids.append(
                relation_id
            )

            tags = relation.get(
                "tags",
                {}
            )

            if tags.get(
                "ref"
            ):

                refs.append(
                    tags.get(
                        "ref"
                    )
                )

            if tags.get(
                "name"
            ):

                directions.append(
                    tags.get(
                        "name"
                    )
                )

            if tags.get(
                "from"
            ):

                from_value = tags.get(
                    "from"
                )

            if tags.get(
                "to"
            ):

                to_value = tags.get(
                    "to"
                )

        ref = (
            group.get(
                "ref"
            )
            or
            (
                refs[0]
                if refs
                else None
            )
        )

        network = group.get(
            "network"
        )

        name = group.get(
            "name"
        )

        if network and ref:

            line_id = (
                f"{network}:"
                f"{ref}"
            )

        else:

            line_id = name

        result.append(
            {

                "line_id":
                    line_id,

                "ref":
                    ref,

                "name":
                    name,

                "network":
                    network,

                "route":
                    group.get(
                        "route"
                    ),

                "from":
                    from_value,

                "to":
                    to_value,

                "directions":
                    directions,

                "relation_ids":
                    relation_ids

            }
        )

    result.sort(
        key=lambda item:
        (
            normalize_ref(
                item.get(
                    "ref"
                )
            ),
            item.get(
                "name",
                ""
            )
        )
    )

    return result