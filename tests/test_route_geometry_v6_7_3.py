from types import SimpleNamespace

import pytest

from metrogis.geometry import route_builder


def _station(name, lng, lat):
    # Match the current MetroGIS Station model: coordinates are exposed as
    # lat/lng fields rather than a dedicated point attribute.
    return SimpleNamespace(
        name=name,
        lng=lng,
        lat=lat,
        order=0,
    )


def _way(way_id, nodes, geometry):
    return {
        "id": way_id,
        "nodes": list(nodes),
        "geometry": [list(point) for point in geometry],
        "tags": {"railway": "subway"},
    }


def _candidate(relation_id, stops, ways, member_refs, name=None):
    return {
        "relation": {
            "id": relation_id,
            "tags": {
                "name": name or f"测试3号线 {relation_id}"
            },
            "members": [
                {
                    "type": "way",
                    "ref": ref,
                    "role": "",
                }
                for ref in member_refs
            ],
        },
        "stops": stops,
        "stop_nodes": {},
        "tracks": ways,
        "relation_way_ids": set(member_refs),
    }


def _line():
    return SimpleNamespace(
        city="测试",
        name="3号线",
        stations=[
            _station("A站", 0.0, 0.0),
            _station("B站", 1.0, 0.0),
            _station("C站", 2.0, 0.0),
        ],
        geometry=[],
        _route_master_main_id=100,
    )


def test_route_master_main_relation_is_preferred(monkeypatch):
    line = _line()

    main = _candidate(
        100,
        [
            {"id": 2, "name": "B站", "point": [1.0, 0.0]},
            {"id": 3, "name": "C站", "point": [2.0, 0.0]},
        ],
        [
            _way(10, [1, 2], [[0.0, 0.0], [1.0, 0.0]]),
            _way(11, [2, 3], [[1.0, 0.0], [2.0, 0.0]]),
        ],
        [10, 11],
        "测试3号线 主",
    )

    branch = _candidate(
        200,
        [
            {"id": 2, "name": "B站", "point": [1.0, 0.0]},
            {"id": 3, "name": "C站", "point": [2.0, 0.0]},
        ],
        [
            _way(20, [1, 2], [[0.0, 0.0], [1.0, 0.0]]),
            _way(21, [2, 3], [[1.0, 0.0], [2.0, 0.0]]),
            _way(22, [3, 4], [[2.0, 0.0], [3.0, 0.0]]),
        ],
        [20, 21, 22],
        "测试3号线 Branch",
    )

    monkeypatch.setattr(
        route_builder,
        "get_line_relation_tracks",
        lambda *args, **kwargs: {
            "candidates": [branch, main],
            "relations": [],
        },
    )

    result = route_builder.build_relation_route(line, (0.0, 0.0, 3.0, 1.0))

    assert result is not None
    assert result["relation_id"] == 100
    assert result["route_master_preferred"] is True


def test_completed_endpoint_is_included_in_geometry():
    line = _line()

    candidate = _candidate(
        100,
        [
            {"id": 2, "name": "B站", "point": [1.0, 0.0]},
            {"id": 3, "name": "C站", "point": [2.0, 0.0]},
        ],
        [
            _way(10, [1, 2], [[0.0, 0.0], [1.0, 0.0]]),
            _way(11, [2, 3], [[1.0, 0.0], [2.0, 0.0]]),
        ],
        [10, 11],
    )

    result = route_builder.evaluate_relation_candidate(
        candidate,
        line.stations,
    )

    assert result is not None
    assert result["projected_station_count"] == 3
    assert result["geometry"][0] == [0.0, 0.0]
    assert result["geometry"][-1] == [2.0, 0.0]
    assert result["length"] > 100000.0
