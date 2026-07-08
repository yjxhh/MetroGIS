import requests


NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


HEADERS = {
    "User-Agent": (
        "MetroGIS/0.2.0 "
        "(https://github.com/yjxhh/MetroGIS)"
    )
}


def search_place(name):
    """
    使用 OpenStreetMap Nominatim 查询地点坐标

    Args:
        name(str): 地点名称，例如 大连站

    Returns:
        dict:
        {
            "name": 地点完整名称,
            "lat": 纬度,
            "lon": 经度
        }

        查询失败返回 None
    """

    if not name:
        return None


    queries = [
        name,
        name.replace("站", ""),
        f"{name} 大连",
        f"{name} 大连市"
    ]


    for query in queries:

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "cn",
            "addressdetails": 1
        }


        try:

            response = requests.get(
                NOMINATIM_URL,
                params=params,
                headers=HEADERS,
                timeout=30
            )

            response.raise_for_status()


        except requests.RequestException:

            continue


        try:

            data = response.json()

        except ValueError:

            continue



        if data:

            item = data[0]

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

            except (
                KeyError,
                ValueError,
                TypeError
            ):

                continue


    return None