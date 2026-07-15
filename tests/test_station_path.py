from metrogis.api.track import (
    get_track_geometry
)

from metrogis.geometry.osm_graph import (
    build_osm_graph
)

from metrogis.geometry.path_finder import (
    nearest_node,
    shortest_path,
    path_geometry
)

from metrogis.geometry.osm_graph import (
    point_distance
)





def geometry_length(
    geometry
):
    """
    计算轨迹长度
    """

    length = 0


    for i in range(
        len(geometry)-1
    ):

        length += point_distance(
            geometry[i],
            geometry[i+1]
        )


    return length





def test_station_path():


    bbox = (

        38.8,
        116.8,
        39.4,
        117.8

    )


    print()

    print(
        "获取OSM轨迹..."
    )


    tracks = get_track_geometry(
        bbox
    )


    print(
        "轨迹数量:",
        len(tracks)
    )



    graph = build_osm_graph(
        tracks
    )


    print(
        "节点数量:",
        len(graph)
    )



    #
    # 天津3号线
    #
    # 南站
    #

    start_point = [

        117.0557201,
        39.0558987

    ]



    #
    # 杨伍庄
    #

    end_point = [

        117.0631925,
        39.0671719

    ]



    start = nearest_node(

        graph,

        start_point

    )


    end = nearest_node(

        graph,

        end_point

    )



    print()

    print(
        "南站 node:",
        start
    )


    print(
        "杨伍庄 node:",
        end
    )



    assert start is not None

    assert end is not None



    path = shortest_path(

        graph,

        start,

        end

    )



    print()

    print(
        "路径节点:",
        len(path)
    )



    assert len(path) > 0



    geometry = path_geometry(

        graph,

        path

    )



    print(
        "轨迹点:",
        len(geometry)
    )



    distance = geometry_length(

        geometry

    )



    print(
        "区间距离:",
        round(
            distance,
            2
        ),
        "米"
    )



    assert len(geometry) > 1


    #
    # 天津3号线站间距离
    # 大约1.8~2公里
    #

    assert distance > 1000

    assert distance < 3000