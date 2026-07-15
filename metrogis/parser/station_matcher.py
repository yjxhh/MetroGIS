"""
MetroGIS Station Matcher

负责官方站名和OSM站名匹配
"""


def normalize_station_name(
    name: str
):

    if not name:

        return ""


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

        .strip()

    )


    if name.endswith(
        "站"
    ):

        name = name[:-1]


    return name



def station_name_score(
    a: str,
    b: str
):

    a = normalize_station_name(
        a
    )


    b = normalize_station_name(
        b
    )


    if not a or not b:

        return 0


    if a == b:

        return 100


    if a in b or b in a:

        return 80


    return 0



def match_station(
    official_name,
    osm_stations,
    threshold=60
):

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