from metrogis.api.track import get_track_geometry
from metrogis.geometry.osm_graph import build_osm_graph


def test_graph_metadata():

    tracks = get_track_geometry(
        (
            38.8,
            116.8,
            39.4,
            117.8
        )
    )

    graph = build_osm_graph(tracks)

    assert len(graph) > 0

    node = next(iter(graph))

    edge = graph[node]["edges"][0]

    assert "node" in edge
    assert "distance" in edge
    assert "way" in edge
    assert "tags" in edge

    print()
    print(edge)