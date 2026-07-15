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



from metrogis.geometry.route_builder import (
    geometry_length
)





def test_osm_path_finder():


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

        117.0558987,

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
        "起点node:",
        start
    )


    print(
        "终点node:",
        end
    )





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





    geometry = path_geometry(
        graph,
        path
    )



    print(
        "轨迹点:",
        len(geometry)
    )





    #
    # 计算真实距离
    #

    distance = geometry_length(
        geometry
    )



    print(
        "路径距离:",
        round(
            distance,
            2
        ),
        "米"
    )





    assert start is not None


    assert end is not None


    assert len(path) > 0


    assert len(geometry) > 0


    assert distance > 0