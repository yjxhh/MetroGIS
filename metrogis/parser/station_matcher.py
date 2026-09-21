"""
MetroGIS Station Matcher

负责官方站名和 OSM 站名匹配

匹配原则:

1. 精确名称优先
2. 支持“站”后缀差异
3. 支持“地铁 / 车站 / 站点”等冗余词
4. 禁止仅因为共享短前缀而产生高分匹配
5. 避免“天津站”匹配到“天津宾馆”这类错误
"""


def _clean_name(
    name: str
):
    """
    基础清洗。

    不在这里直接删除最后一个“站”，
    因为“天津站”与“天津宾馆”的区别非常重要。
    """

    if not name:

        return ""

    name = str(
        name
    )

    name = (
        name
        .replace(
            "地铁",
            ""
        )
        .replace(
            "轨道交通",
            ""
        )
        .replace(
            "车站",
            ""
        )
        .replace(
            "站点",
            ""
        )
        .replace(
            " ",
            ""
        )
        .replace(
            "　",
            ""
        )
        .strip()
    )

    return name


def _name_variants(
    name: str
):
    """
    生成站名候选形式。

    例如:

        天津站

    得到:

        天津站
        天津

    这样既支持“站”后缀差异，
    又不会把“天津宾馆”当成“天津站”。
    """

    base = _clean_name(
        name
    )

    if not base:

        return set()

    variants = {
        base
    }

    #
    # 只有真正以“站”结尾时，
    # 才增加去掉“站”的形式。
    #
    if base.endswith(
        "站"
    ) and len(base) > 2:

        variants.add(
            base[:-1]
        )

    return variants


def normalize_station_name(
    name: str
):
    """
    返回主要标准化站名。

    保留“站”本身。
    """

    variants = _name_variants(
        name
    )

    if not variants:

        return ""

    #
    # 优先返回最长形式，
    # 避免“天津站”直接变成“天津”。
    #
    return max(
        variants,
        key=len
    )


def station_name_score(
    a: str,
    b: str
):
    """
    计算两个站名的匹配分数。

    100:
        精确匹配

    95:
        一个名称只是多/少了最后“站”

    80:
        合理的完整名称包含关系

    0:
        不匹配

    特别规则:

        “天津站”
        与
        “天津宾馆”

        不允许因为共享“天津”而匹配。
    """

    if not a or not b:

        return 0

    a_base = _clean_name(
        a
    )

    b_base = _clean_name(
        b
    )

    if not a_base or not b_base:

        return 0

    #
    # --------------------------------------------------
    # 1. 完全相同
    # --------------------------------------------------
    #

    if a_base == b_base:

        return 100

    #
    # --------------------------------------------------
    # 2. 只差一个末尾“站”
    # --------------------------------------------------
    #

    a_no_station = (
        a_base[:-1]
        if a_base.endswith("站")
        else a_base
    )

    b_no_station = (
        b_base[:-1]
        if b_base.endswith("站")
        else b_base
    )

    if (
        a_no_station == b_no_station
        and
        a_no_station
    ):

        return 95

    #
    # --------------------------------------------------
    # 3. 完整名称包含
    # --------------------------------------------------
    #
    # 不能对只有 1~2 个字符的短名称进行包含匹配。
    #
    # 例如:
    #
    # 天津
    #    ↓
    # 天津宾馆
    #
    # 这种必须拒绝。
    #
    # 只有较长的站名才允许包含匹配。
    #
    shorter = min(
        len(a_base),
        len(b_base)
    )

    if shorter >= 3:

        if a_base in b_base:

            #
            # 长度差过大时拒绝。
            #
            if (
                len(b_base)
                -
                len(a_base)
                <= 3
            ):

                return 80

        if b_base in a_base:

            if (
                len(a_base)
                -
                len(b_base)
                <= 3
            ):

                return 80

    #
    # --------------------------------------------------
    # 不匹配
    # --------------------------------------------------
    #

    return 0


def match_station(
    official_name,
    osm_stations,
    threshold=60
):
    """
    在 OSM 站点列表中匹配官方站名。

    同分时保留第一个候选。

    注意:

    本函数只负责名称匹配。
    如果存在多个完全同名 OSM 站点，
    上层可以继续使用空间信息进行消歧。
    """

    best = None

    best_score = 0

    for station in osm_stations:

        #
        # 兼容不同数据结构
        #
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

        if score > best_score:

            best_score = score

            best = station

    if best_score >= threshold:

        return best

    return None