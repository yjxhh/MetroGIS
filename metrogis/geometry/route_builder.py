"""
MetroGIS Route Builder V4.1.1

根据官方运营顺序
匹配 OSM 轨迹

功能:

1. 官方站点顺序
2. OSM轨迹匹配
3. 米制距离计算
4. TrackPoint输出
5. 区间长度调试
"""


from pyproj import Transformer


from metrogis.provider.osm import (
    get_osm_geometry
)


#
# 经纬度 -> 米
#
transformer = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:3857",
    always_xy=True
)



def point_distance(
    a,
    b
):
    """
    两点距离 米
    """

    ax, ay = transformer.transform(
        a[0],
        a[1]
    )

    bx, by = transformer.transform(
        b[0],
        b[1]
    )


    return (
        (ax-bx)**2 +
        (ay-by)**2
    ) ** 0.5





def geometry_length(
    geometry
):
    """
    计算轨迹长度
    """

    total = 0


    for i in range(
        len(geometry)-1
    ):

        total += point_distance(
            geometry[i],
            geometry[i+1]
        )


    return total





def nearest_index(
    geometry,
    point
):
    """
    找最近节点
    """


    index = None

    minimum = float(
        "inf"
    )


    for i,p in enumerate(
        geometry
    ):

        d = point_distance(
            p,
            point
        )


        if d < minimum:

            minimum = d

            index = i


    return index, minimum






def cut_segment(
    geometry,
    start,
    end
):
    """
    根据两个站点截取轨迹
    """


    s, sd = nearest_index(
        geometry,
        start
    )


    e, ed = nearest_index(
        geometry,
        end
    )


    if s is None or e is None:

        return [],999999



    if s <= e:

        segment = geometry[
            s:e+1
        ]

    else:

        segment = list(
            reversed(
                geometry[e:s+1]
            )
        )


    return (
        segment,
        sd + ed
    )







def calculate_score(
    segment,
    error,
    start,
    end
):
    """
    匹配评分
    """


    if len(segment)<2:

        return -1



    real_length = geometry_length(
        segment
    )


    direct = point_distance(
        start,
        end
    )


    if direct == 0:

        return -1



    ratio = (
        real_length /
        direct
    )



    #
    # 地铁线路长度比例
    #

    if ratio < 0.7:

        return -1


    if ratio > 5:

        return -1



    length_score = (
        100 -
        abs(
            ratio-1.5
        )*30
    )



    error_score = (
        1000 /
        (
            error+1
        )
    )



    point_score = min(
        len(segment),
        200
    )


    return (
        length_score
        +
        error_score
        +
        point_score
    )







def build_route_geometry(
    line,
    bbox
):
    """
    根据Line对象生成完整轨迹
    """


    print(
        "获取OSM轨迹..."
    )


    tracks = get_osm_geometry(
        bbox
    )


    print(
        "轨迹数量:",
        len(tracks)
    )



    route=[]



    stations = line.stations



    for i in range(
        len(stations)-1
    ):


        start=[
            stations[i].lng,
            stations[i].lat
        ]


        end=[
            stations[i+1].lng,
            stations[i+1].lat
        ]



        print(
            "匹配:",
            stations[i].name,
            "->",
            stations[i+1].name
        )



        best=None

        best_score=-1



        best_id=None



        for track in tracks:


            segment,error = cut_segment(

                track["geometry"],

                start,

                end

            )



            score = calculate_score(

                segment,

                error,

                start,

                end

            )



            if score > best_score:

                best_score = score

                best = segment

                best_id = track["id"]





        if best:


            length = geometry_length(
                best
            )


            print(
                "  way:",
                best_id,
                "长度:",
                round(
                    length,
                    2
                ),
                "米"
            )



            if route:

                route.extend(
                    best[1:]
                )

            else:

                route.extend(
                    best
                )




    #
    # 总长度
    #

    total = geometry_length(
        route
    )


    print(
        "线路长度:",
        round(
            total,
            2
        ),
        "米"
    )




    #
    # 写入 TrackPoint
    #

    line.geometry=[]


    distance=0



    for i,p in enumerate(
        route
    ):


        if i>0:

            distance += point_distance(
                route[i-1],
                p
            )


        line.add_geometry_point(

            p[0],

            p[1],

            round(
                distance,
                2
            )

        )


    return line