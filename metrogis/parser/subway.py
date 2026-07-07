"""
MetroGIS Subway Parser

负责把 Overpass 返回的数据
转换成 MetroGIS 标准格式
"""


def parse_subway_line(data: dict):
    """
    解析 Overpass 地铁线路数据

    参数:
        data:
            Overpass API 返回 JSON

    返回:
        MetroGIS 标准线路对象
    """

    result = {
        "line": None,
        "stations": [],
        "geometry": []
    }


    elements = data.get(
        "elements",
        []
    )


    for element in elements:

        tags = element.get(
            "tags",
            {}
        )


        # 获取线路名称
        if (
            element.get("type") == "relation"
            and tags.get("route") == "subway"
        ):

            result["line"] = tags.get(
                "name"
            )


        # 获取站点
        if (
            tags.get("railway") == "station"
            or tags.get("station") == "subway"
        ):

            station = {
                "name": tags.get(
                    "name"
                ),
                "lat": element.get(
                    "lat"
                ),
                "lng": element.get(
                    "lon"
                )
            }

            result["stations"].append(
                station
            )


    return result
