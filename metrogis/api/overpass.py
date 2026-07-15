"""
MetroGIS Overpass API

负责从 OpenStreetMap Overpass API
获取地铁线路数据
"""

import time
import requests

from .nominatim import get_city_bbox


OVERPASS_SERVERS = [

    "https://overpass-api.de/api/interpreter",

    "https://overpass.kumi.systems/api/interpreter",

    "https://overpass.private.coffee/api/interpreter"

]


HEADERS = {

    "User-Agent":

    "MetroGIS/0.3.0 (https://github.com/yjxhh/MetroGIS)"

}


def query_overpass(
    query: str,
    retry: int = 3
):

    last_error = None

    for server in OVERPASS_SERVERS:

        for index in range(retry):

            try:

                print(
                    f"Query Overpass: {server}"
                )

                response = requests.post(

                    server,

                    data={
                        "data": query
                    },

                    headers=HEADERS,

                    timeout=180

                )

                response.raise_for_status()

                return response.json()

            except Exception as e:

                last_error = e

                print(
                    f"failed {index + 1}/{retry}: {e}"
                )

                time.sleep(3)

    raise RuntimeError(last_error)


def build_query(
    line_name: str,
    bbox
):
    """
    生成 Overpass Query
    """

    south, west, north, east = bbox

    bbox_text = (
        f"{south},"
        f"{west},"
        f"{north},"
        f"{east}"
    )

    return f"""
[out:json][timeout:180];

(

relation
["route"="subway"]
["name"~"{line_name}"]
({bbox_text});

relation
["route"="light_rail"]
["name"~"{line_name}"]
({bbox_text});

relation
["route"="railway"]
["name"~"{line_name}"]
({bbox_text});

);

out body;
>;
out geom;
"""


def search_metro_line(
    line_name: str,
    city: str = "大连"
):
    """
    查询城市地铁线路

    Parameters
    ----------
    line_name
        如：
        13号线
        大连地铁13号线
        Line 2

    city
        城市名称
    """

    bbox = get_city_bbox(city)

    if bbox is None:

        raise RuntimeError(
            f"无法获取城市边界：{city}"
        )

    print(
        f"City: {city}"
    )

    print(
        f"BBox: {bbox}"
    )

    query = build_query(
        line_name,
        bbox
    )

    data = query_overpass(
        query
    )

    print(
        "Elements:",
        len(
            data.get(
                "elements",
                []
            )
        )
    )

    return data
def list_metro_lines(
    city: str
):
    """
    查询指定城市所有城市轨道交通线路

    V2.1 全国版

    特性:
    - 合并同线路不同方向 relation
    - 去除重复方向
    - OSM 名称标准化
    - 不绑定任何城市规则
    - 支持 subway/light_rail/tram

    返回:
    [
        {
            "line_id": "",
            "ref": "",
            "name": "",
            "network": "",
            "route": "",
            "from": "",
            "to": "",
            "directions": 2
        }
    ]
    """

    from .nominatim import search_place


    place = search_place(
        city
    )


    if place is None:

        raise RuntimeError(
            f"无法定位城市: {city}"
        )


    lat = float(
        place["lat"]
    )

    lon = float(
        place["lon"]
    )


    #
    # 城市搜索范围
    #
    # 后续 V2.2 会接入行政边界
    #

    south = lat - 0.9

    north = lat + 0.9

    west = lon - 1.2

    east = lon + 1.2



    bbox = (
        f"{south},"
        f"{west},"
        f"{north},"
        f"{east}"
    )


    print(
        "City:",
        city
    )

    print(
        "BBox:",
        (
            south,
            west,
            north,
            east
        )
    )



    query = f"""

[out:json][timeout:180];

(

relation
["route"="subway"]
({bbox});

relation
["route"="light_rail"]
({bbox});

relation
["route"="tram"]
({bbox});

);

out tags;

"""


    data = query_overpass(
        query
    )



    #
    # 线路名称标准化
    #

    def normalize_name(
        name
    ):

        if not name:

            return ""


        name = (
            name
            .replace(
                "：",
                ":"
            )
            .strip()
        )


        #
        # 去方向
        #

        if ":" in name:

            name = name.split(
                ":",
                1
            )[0]


        return (
            name
            .replace(
                " ",
                ""
            )
            .strip()
        )



    #
    # 线路唯一标识
    #

    def build_line_key(
        tags
    ):

        network = tags.get(
            "network",
            ""
        )


        ref = tags.get(
            "ref",
            ""
        )


        name = normalize_name(
            tags.get(
                "name",
                ""
            )
        )


        #
        # 优先 network + ref
        #

        if network and ref:

            return (
                network,
                ref
            )


        #
        # 其次 name
        #

        return (
            network,
            name
        )



    lines = {}



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



        raw_name = tags.get(
            "name",
            ""
        )


        if not raw_name:

            continue



        route = tags.get(
            "route",
            ""
        )


        name = normalize_name(
            raw_name
        )


        ref = tags.get(
            "ref",
            ""
        )


        network = tags.get(
            "network",
            ""
        )



        key = build_line_key(
            tags
        )



        direction = (

            tags.get(
                "from",
                ""
            ),

            tags.get(
                "to",
                ""
            )

        )



        if key not in lines:


            lines[key] = {

                "line_id":
                    None,


                "ref":
                    ref,


                "name":
                    name,


                "network":
                    network,


                "route":
                    route,


                "from":
                    direction[0],


                "to":
                    direction[1],


                "_directions":
                    set()

            }



        #
        # 收集方向
        #

        if direction != (
            "",
            ""
        ):

            lines[key][
                "_directions"
            ].add(
                direction
            )



    result = []



    for item in lines.values():


        directions = item.pop(
            "_directions"
        )


        item["directions"] = len(
            directions
        )


        if item["directions"] == 0:

            item["directions"] = 1



        #
        # 生成稳定 line_id
        #

        item["line_id"] = (

            item["network"]

            + "_"

            + (

                item["ref"]

                if item["ref"]

                else item["name"]

            )

        )


        result.append(
            item
        )



    #
    # 排序
    #

    def sort_key(
        item
    ):

        ref = item.get(
            "ref",
            ""
        )


        try:

            return (
                0,
                int(
                    ref
                )
            )

        except Exception:

            return (
                1,
                ref
            )



    result.sort(
        key=sort_key
    )



    return result