"""
MetroGIS Nominatim API

负责使用 OpenStreetMap Nominatim
查询地点、城市等地理信息。
"""

import requests


NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


HEADERS = {
    "User-Agent": (
        "MetroGIS/0.3.0 "
        "(https://github.com/yjxhh/MetroGIS)"
    )
}


def _request(query: str):
    """
    内部查询函数
    """

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "polygon_geojson": 0,
        "addressdetails": 1,
        "countrycodes": "cn"
    }

    try:

        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if data:
            return data[0]

    except Exception:

        return None

    return None


def search_place(name):
    """
    查询地点

    Args:
        name:
            地点名称

    Returns:
        {
            name,
            lat,
            lon
        }

        查询失败返回 None
    """

    if not name:
        return None

    queries = [
        name,
        name.replace("站", ""),
        f"{name} 中国"
    ]

    for query in queries:

        item = _request(query)

        if not item:
            continue

        try:

            return {

                "name": item.get(
                    "display_name",
                    query
                ),

                "lat": float(
                    item["lat"]
                ),

                "lon": float(
                    item["lon"]
                )

            }

        except Exception:

            continue

    return None


def search_city(city):
    """
    查询城市

    返回：

    {
        name,
        lat,
        lon,
        bbox
    }
    """

    if not city:

        return None

    queries = [

        city,

        f"{city}市",

        f"{city} 中国"

    ]

    for query in queries:

        item = _request(query)

        if not item:

            continue

        try:

            bbox = [

                float(item["boundingbox"][0]),

                float(item["boundingbox"][1]),

                float(item["boundingbox"][2]),

                float(item["boundingbox"][3])

            ]

            return {

                "name": item.get(
                    "display_name",
                    city
                ),

                "lat": float(
                    item["lat"]
                ),

                "lon": float(
                    item["lon"]
                ),

                "bbox": bbox

            }

        except Exception:

            continue

    return None


def get_city_bbox(city):
    """
    获取城市 Bounding Box

    返回：

    south,
    west,
    north,
    east
    """

    info = search_city(city)

    if not info:

        return None

    south = info["bbox"][0]

    north = info["bbox"][1]

    west = info["bbox"][2]

    east = info["bbox"][3]

    return (
        south,
        west,
        north,
        east
    )