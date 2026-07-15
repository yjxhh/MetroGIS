from metrogis.api.track import get_track_geometry

from metrogis.geometry.osm_graph import build_osm_graph

from metrogis.geometry.path_finder import (
    build_spatial_index,
    nearest_node
)



def test_spatial_index():


    tracks=get_track_geometry(
        (
            38.8,
            116.8,
            39.4,
            117.8
        )
    )


    graph=build_osm_graph(
        tracks
    )


    index=build_spatial_index(
        graph
    )


    node=nearest_node(
        graph,
        [
            117.0558987,
            39.0558987
        ],
        index
    )


    print()

    print(
        "nearest:",
        node
    )


    assert node is not None