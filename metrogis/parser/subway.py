"""
MetroGIS Subway Parser

负责把 Overpass 返回的数据
转换成 MetroGIS 标准格式

V2:
- 线路名称标准化
- relation 合并
- 城市过滤
- 方向去重
"""


from collections import defaultdict



# ==============================
# 线路名称标准化
# ==============================

def normalize_line_name(name: str, ref: str = ""):
    """
    标准化线路名称

    示例:
    地铁 1号线
    地铁1号线
    地铁 八通线

    """

    if not name:
        return None


    name = (
        name
        .replace(
            "地铁 ",
            "地铁"
        )
        .strip()
    )


    # 北京1号线特殊处理
    if ref in [
        "1",
        "1E"
    ]:
        return "北京地铁1号线/八通线"


    return name



# ==============================
# bbox过滤
# ==============================

def point_in_bbox(
    lat,
    lng,
    bbox
):
    """
    判断坐标是否在城市范围

    bbox:
    south,west,north,east
    """

    south, west, north, east = bbox


    return (
        south <= lat <= north
        and
        west <= lng <= east
    )



def filter_stations_by_bbox(
    stations,
    bbox
):

    result = []


    for s in stations:

        lat = s.get(
            "lat"
        )

        lng = s.get(
            "lng"
        )


        if (
            lat is None
            or
            lng is None
        ):
            continue


        if point_in_bbox(
            lat,
            lng,
            bbox
        ):
            result.append(
                s
            )


    return result




# ==============================
# 基础解析
# ==============================

def parse_subway_line(data: dict):

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


        if (
            element.get("type")
            ==
            "relation"
            and
            tags.get("route")
            ==
            "subway"
        ):

            result["line"] = normalize_line_name(
                tags.get("name"),
                tags.get("ref","")
            )


        if (
            tags.get("railway")
            ==
            "station"
            or
            tags.get("station")
            ==
            "subway"
        ):

            station = {

                "name":
                    tags.get("name"),

                "lat":
                    element.get("lat"),

                "lng":
                    element.get("lon")
            }


            result["stations"].append(
                station
            )


    return result




# ==============================
# V2 多线路解析
# ==============================

def parse_subway_lines_v2(
    data: dict,
    bbox=None
):
    """
    解析多个 subway relation

    返回:
    [
      {
       name:"",
       ref:"",
       stations:[],
       directions:2
      }
    ]
    """


    lines = defaultdict(
        lambda:{
            "name":None,
            "ref":"",
            "stations":[],
            "relations":0
        }
    )


    elements = data.get(
        "elements",
        []
    )


    for element in elements:


        tags = element.get(
            "tags",
            {}
        )


        # relation
        if (
            element.get("type")
            ==
            "relation"
            and
            tags.get("route")
            ==
            "subway"
        ):

            ref = tags.get(
                "ref",
                ""
            )


            name = normalize_line_name(
                tags.get("name"),
                ref
            )


            key = (
                ref
                or
                name
            )


            lines[key]["name"] = name

            lines[key]["ref"] = ref

            lines[key]["relations"] += 1



        # station
        elif (
            tags.get("railway")
            ==
            "station"
            or
            tags.get("station")
            ==
            "subway"
        ):


            station = {

                "name":
                    tags.get("name"),

                "lat":
                    element.get("lat"),

                "lng":
                    element.get("lon")

            }


            for line in lines.values():

                line["stations"].append(
                    station
                )



    result=[]


    for line in lines.values():


        stations=line["stations"]


        if bbox:

            stations = filter_stations_by_bbox(
                stations,
                bbox
            )


        if not stations:
            continue



        # 去重站点

        unique=[]

        exists=set()


        for s in stations:

            key=(
                s["name"],
                s["lat"],
                s["lng"]
            )


            if key not in exists:

                exists.add(key)

                unique.append(
                    s
                )


        line["stations"]=unique


        # 方向合并

        line["directions"]=2


        result.append(
            line
        )



    return result