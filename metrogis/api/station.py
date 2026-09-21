"""
MetroGIS Station API

负责:

1. 查询 OpenStreetMap 地铁站点
2. 支持 railway=station
3. 支持 railway=stop
4. 支持 subway=yes
5. 支持 public_transport=stop_position
6. 官方站名 -> OSM站名匹配
7. 处理同名 OSM 站点
8. 保持官方线路站点顺序
"""

from math import cos, radians

from .overpass import query_overpass

from ..resources.loader import (
    get_station_list
)

from ..resources.override import (
    get_override_station
)

from ..parser.station_matcher import (
    station_name_score
)


#
# --------------------------------------------------
# OSM Station Query
# --------------------------------------------------
#

def build_station_query(
    city_bbox
):
    """
    构建 OSM 地铁站查询。

    city_bbox:

        south, west, north, east

    查询以下类型:

    1. railway=station + station=subway
    2. railway=station + subway=yes
    3. railway=stop + subway=yes
    4. public_transport=stop_position + subway=yes

    第 3 / 4 类尤其重要。

    很多 OSM 地铁站的实际站点节点
    使用:

        railway=stop
        subway=yes

    而不是:

        railway=station
    """

    south, west, north, east = city_bbox

    return f"""

[out:json][timeout:180];

(
    node
    [
        railway="station"
    ]
    [
        station="subway"
    ]
    ({south},{west},{north},{east});

    node
    [
        railway="station"
    ]
    [
        subway="yes"
    ]
    ({south},{west},{north},{east});

    node
    [
        railway="stop"
    ]
    [
        subway="yes"
    ]
    ({south},{west},{north},{east});

    node
    [
        public_transport="stop_position"
    ]
    [
        subway="yes"
    ]
    ({south},{west},{north},{east});
);

out body;

"""


#
# --------------------------------------------------
# 获取 OSM 全部地铁站
# --------------------------------------------------
#

def get_osm_stations(
    bbox
):
    """
    获取城市范围内全部 OSM 地铁站。

    返回:

    [
        {
            "id": ...,
            "name": ...,
            "lat": ...,
            "lng": ...,
            "tags": {...}
        }
    ]
    """

    query = build_station_query(
        bbox
    )

    data = query_overpass(
        query
    )

    stations = []

    #
    # 防止同一个 node 因为多个查询条件
    # 被返回多次。
    #
    seen_ids = set()

    #
    # 同时防止完全相同坐标重复。
    #
    seen_points = set()

    for element in data.get(
        "elements",
        []
    ):

        element_id = element.get(
            "id"
        )

        #
        # node ID 去重
        #
        if element_id is not None:

            if element_id in seen_ids:

                continue

            seen_ids.add(
                element_id
            )

        tags = element.get(
            "tags",
            {}
        )

        name = tags.get(
            "name"
        )

        if not name:

            continue

        lat = element.get(
            "lat"
        )

        lng = element.get(
            "lon"
        )

        if lat is None or lng is None:

            continue

        #
        # 坐标去重
        #
        point_key = (

            round(
                float(lat),
                7
            ),

            round(
                float(lng),
                7
            ),

            str(name).strip()

        )

        if point_key in seen_points:

            continue

        seen_points.add(
            point_key
        )

        stations.append(
            {
                "id": element_id,

                "name": name,

                "lat": float(lat),

                "lng": float(lng),

                "tags": dict(
                    tags
                )
            }
        )

    return stations


#
# --------------------------------------------------
# 米制距离
# --------------------------------------------------
#

def _point_distance(
    a,
    b
):
    """
    近似计算两经纬度点之间的距离。

    返回:
        米
    """

    if a is None or b is None:

        return float(
            "inf"
        )

    lon1, lat1 = a

    lon2, lat2 = b

    lat_scale = 111000.0

    lon_scale = (
        111000.0
        *
        cos(
            radians(
                (
                    lat1 +
                    lat2
                ) / 2
            )
        )
    )

    dx = (
        lon2 -
        lon1
    ) * lon_scale

    dy = (
        lat2 -
        lat1
    ) * lat_scale

    return (
        dx * dx +
        dy * dy
    ) ** 0.5


#
# --------------------------------------------------
# 获取一个官方站名的全部候选
# --------------------------------------------------
#

def _station_candidates(
    official_name,
    osm_stations,
    threshold=60
):
    """
    获取官方站名对应的所有 OSM 候选。
    """

    candidates = []

    for station in osm_stations:

        osm_name = (

            station.get(
                "name"
            )

            or station.get(
                "osm_name"
            )

            or station.get(
                "official_name"
            )

        )

        score = station_name_score(
            official_name,
            osm_name
        )

        if score < threshold:

            continue

        candidates.append(
            {
                "station": station,

                "score": score
            }
        )

    #
    # 优先:
    #
    # 100 精确
    # 95 只差“站”
    # 80 模糊
    #
    candidates.sort(
        key=lambda item: (
            -item["score"],

            item["station"].get(
                "name",
                ""
            ),

            item["station"].get(
                "id",
                0
            )
        )
    )

    return candidates


#
# --------------------------------------------------
# 按线路顺序进行空间匹配
# --------------------------------------------------
#

def _match_station_sequence(
    official_stations,
    osm_stations,
    threshold=60
):
    """
    根据官方线路顺序，在多个 OSM 同名候选中
    选择空间上连续的一组站点。

    用途:

        天津站

        OSM 可能有多个 stop_position

    不再简单使用:

        第一个返回结果

    而是根据相邻站点空间距离进行选择。
    """

    candidate_sets = []

    for official_name in official_stations:

        candidates = _station_candidates(
            official_name,
            osm_stations,
            threshold=threshold
        )

        candidate_sets.append(
            candidates
        )

    #
    # 连续匹配区间
    #
    result = {}

    run_start = None

    for i in range(
        len(official_stations) + 1
    ):

        at_end = (
            i ==
            len(official_stations)
        )

        has_candidates = (

            not at_end

            and

            bool(
                candidate_sets[i]
            )

        )

        #
        # 连续区间开始
        #
        if has_candidates:

            if run_start is None:

                run_start = i

            continue

        #
        # 没有候选，结束当前区间
        #
        if run_start is None:

            continue

        run_end = i

        selected = _solve_station_run(
            official_stations[
                run_start:run_end
            ],

            candidate_sets[
                run_start:run_end
            ]
        )

        for offset, station in selected.items():

            official_name = (
                official_stations[
                    run_start + offset
                ]
            )

            result[
                official_name
            ] = station

        run_start = None

    return result


#
# --------------------------------------------------
# 动态规划
# --------------------------------------------------
#

def _solve_station_run(
    official_names,
    candidate_sets
):
    """
    对连续站点进行空间连续性优化。

    精确名称优先。

    同名站点之间:
        相邻站点距离越合理越优先。
    """

    if not candidate_sets:

        return {}

    #
    # 第一层
    #
    dp = []

    first_states = []

    for item in candidate_sets[0]:

        score = item[
            "score"
        ]

        name_penalty = (
            100 -
            score
        ) * 1000.0

        first_states.append(
            {
                "cost": name_penalty,

                "prev": None
            }
        )

    dp.append(
        first_states
    )

    #
    # 后续层
    #
    for i in range(
        1,
        len(candidate_sets)
    ):

        current_states = []

        for current_item in candidate_sets[i]:

            current_station = current_item[
                "station"
            ]

            current_point = (

                current_station.get(
                    "lng"
                ),

                current_station.get(
                    "lat"
                )

            )

            score = current_item[
                "score"
            ]

            name_penalty = (
                100 -
                score
            ) * 1000.0

            best_cost = float(
                "inf"
            )

            best_prev = None

            for prev_index, prev_item in enumerate(
                candidate_sets[i - 1]
            ):

                previous_station = prev_item[
                    "station"
                ]

                previous_point = (

                    previous_station.get(
                        "lng"
                    ),

                    previous_station.get(
                        "lat"
                    )

                )

                distance = _point_distance(
                    previous_point,
                    current_point
                )

                cost = (

                    dp[i - 1][prev_index][
                        "cost"
                    ]

                    +

                    distance

                    +

                    name_penalty

                )

                if cost < best_cost:

                    best_cost = cost

                    best_prev = prev_index

            current_states.append(
                {
                    "cost": best_cost,

                    "prev": best_prev
                }
            )

        dp.append(
            current_states
        )

    #
    # 最后一层最优
    #
    best_last = min(
        range(
            len(
                dp[-1]
            )
        ),

        key=lambda index:
        dp[-1][index]["cost"]
    )

    #
    # 回溯
    #
    selected_indices = [
        None
    ] * len(
        candidate_sets
    )

    current_index = best_last

    for i in range(
        len(candidate_sets) - 1,
        -1,
        -1
    ):

        selected_indices[i] = (
            current_index
        )

        current_index = dp[i][
            current_index
        ]["prev"]

        if (
            i > 0
            and
            current_index is None
        ):

            break

    #
    # 生成结果
    #
    result = {}

    for i, candidate_index in enumerate(
        selected_indices
    ):

        if candidate_index is None:

            continue

        result[i] = candidate_sets[i][
            candidate_index
        ]["station"]

    return result


#
# --------------------------------------------------
# 指定线路站点
# --------------------------------------------------
#

def get_line_stations(
    city,
    line,
    bbox
):
    """
    获取指定线路运营站点对应的 OSM 坐标。

    返回:

    [
        {
            "official_name": "...",

            "osm_name": "...",

            "lat": ...,

            "lng": ...,

            "osm_id": ...
        }
    ]
    """

    #
    # 官方站点顺序
    #
    official_stations = get_station_list(
        city,
        line
    )

    if not official_stations:

        raise RuntimeError(
            f"没有找到线路数据: "
            f"{city} {line}"
        )

    #
    # OSM 全部地铁站
    #
    osm_stations = get_osm_stations(
        bbox
    )

    print(
        "OSM地铁站数量:",
        len(osm_stations)
    )

    #
    # 整条线路整体匹配
    #
    matched_map = _match_station_sequence(
        official_stations,
        osm_stations
    )

    result = []

    #
    # 按官方站点顺序输出
    #
    for name in official_stations:

        station = matched_map.get(
            name
        )

        if station:

            result.append(
                {
                    "official_name": name,

                    "osm_name": station.get(
                        "name"
                    ),

                    "lat": station.get(
                        "lat"
                    ),

                    "lng": station.get(
                        "lng"
                    ),

                    "osm_id": station.get(
                        "id"
                    )
                }
            )

            continue

        #
        # OSM 没找到，尝试人工坐标
        #
        override = get_override_station(
            city,
            line,
            name
        )

        if override is not None:

            print(
                "使用人工坐标:",
                city,
                line,
                name
            )

            result.append(
                {
                    "official_name": name,

                    "osm_name": None,

                    "lat": override[
                        "lat"
                    ],

                    "lng": override[
                        "lng"
                    ],

                    "osm_id": None
                }
            )

            continue

        print(
            "缺少坐标:",
            city,
            line,
            name
        )

    return result