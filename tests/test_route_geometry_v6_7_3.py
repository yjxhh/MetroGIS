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



def test_related_geometry_chain_prefers_route_master_osm_stop_id():
    candidate = _candidate(
        500,
        [
            {"id": 1, "name": "A站", "point": [0.0, 0.0]},
            {"id": 2, "name": "B站", "point": [1.0, 0.0]},
            {"id": 3, "name": "C站", "point": [2.0, 0.0]},
        ],
        [
            # Correct route starts at OSM stop node 1.
            _way(10, [1, 2], [[0.0, 0.0], [1.0, 0.0]]),
            _way(11, [2, 3], [[1.0, 0.0], [2.0, 0.0]]),
            # This Way is geographically closer to A, but is not connected
            # through the authoritative OSM stop node id.
            _way(99, [90, 91], [[0.00001, 0.0], [0.00002, 0.0]]),
        ],
        [10, 11, 99],
        "测试3号线：A站 → C站",
    )

    route_stations = [
        {"id": 1, "name": "A站", "point": [0.0, 0.0]},
        {"id": 2, "name": "B站", "point": [1.0, 0.0]},
        {"id": 3, "name": "C站", "point": [2.0, 0.0]},
    ]

    result = route_builder.evaluate_relation_candidate(
        candidate,
        route_stations,
    )

    assert result is not None
    assert result["chain"]["way_ids"] == [10, 11]
    assert result["chain"]["used_way_count"] == 2
    assert result["chain"]["total_way_count"] == 3
    assert result["chain"]["continuous"] is True

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


def test_build_route_geometry_exposes_quality_metadata(monkeypatch):
    line = _line()

    relation_result = {
        "relation_id": 100,
        "relation_name": "测试3号线 主",
        "route_master_preferred": True,
        "geometry": [[0.0, 0.0], [0.0001, 0.0]],
        "length": 11.1,
        "projected_station_count": 3,
        "max_snap": 12.5,
        "snap_sum": 20.0,
        "monotonic_failures": 0,
        "chain": {
            "way_ids": [10, 11],
            "used_way_count": 2,
            "total_way_count": 2,
            "connected": True,
        },
    }

    monkeypatch.setattr(
        route_builder,
        "build_relation_route",
        lambda line, bbox: relation_result,
    )

    result = route_builder.build_route_geometry(
        line,
        (0.0, 0.0, 1.0, 1.0),
    )

    assert result is line
    assert line.geometry == [[0.0, 0.0], [0.0001, 0.0]]
    assert line.geometry_relation_id == 100
    assert line.geometry_route_master_preferred is True
    assert line.geometry_way_ids == [10, 11]
    assert line.geometry_used_way_count == 2
    assert line.geometry_total_way_count == 2
    assert line.geometry_connected is True
    assert line.geometry_projected_station_count == 3
    expected_projection = route_builder._station_sequence_positions(
        line.stations,
        line.geometry,
    )
    assert line.geometry_max_snap == expected_projection["max_snap"]
    assert line.geometry_station_monotonic_failures == expected_projection[
        "monotonic_failures"
    ]


def test_route_master_endpoint_geometry_completion_uses_recorded_evidence():
    line = SimpleNamespace(
        city="测试",
        name="3号线",
        stations=[
            SimpleNamespace(name="A站", lng=0.0, lat=0.0, order=0),
            SimpleNamespace(name="B站", lng=1.0, lat=0.0, order=1),
            SimpleNamespace(name="C站", lng=2.0, lat=0.0, order=2),
        ],
        geometry=[],
        _route_master={
            "completion": {
                "main": {
                    "added_count": 2,
                    "declared_start": "A站",
                    "declared_end": "C站",
                    "start_evidence_relation_ids": [200],
                    "end_evidence_relation_ids": [300],
                }
            }
        },
    )

    main = _candidate(
        100,
        [
            {"id": 11, "name": "B站", "point": [1.0, 0.0]},
            {"id": 12, "name": "C内侧", "point": [2.0, 0.0]},
        ],
        [
            _way(101, [1, 2], [[1.0, 0.0], [2.0, 0.0]]),
        ],
        [101],
        "测试3号线：B站 → C站",
    )

    start_evidence = _candidate(
        200,
        [
            {"id": 10, "name": "A站", "point": [0.0, 0.0]},
            {"id": 11, "name": "B站", "point": [1.0, 0.0]},
        ],
        [
            _way(201, [10, 11], [[0.0, 0.0], [1.0, 0.0]]),
        ],
        [201],
        "测试3号线：A站 → B站",
    )

    end_evidence = _candidate(
        300,
        [
            {"id": 12, "name": "C内侧", "point": [2.0, 0.0]},
            {"id": 13, "name": "C站", "point": [3.0, 0.0]},
        ],
        [
            _way(301, [12, 13], [[2.0, 0.0], [3.0, 0.0]]),
        ],
        [301],
        "测试3号线：C内侧 → C站",
    )

    result = {
        "relation_id": 100,
        "relation_name": "测试3号线：A站 → C站",
        "route_master_preferred": True,
        "candidate": main,
        "geometry": [[1.0, 0.0], [2.0, 0.0]],
        "length": route_builder.geometry_length([[1.0, 0.0], [2.0, 0.0]]),
        "chain": {
            "way_ids": [101],
            "used_way_count": 1,
            "total_way_count": 1,
            "connected": True,
        },
    }

    enriched = route_builder._apply_route_master_endpoint_geometry_completion(
        line,
        result,
        [main, start_evidence, end_evidence],
    )

    assert enriched["start_added"] is True
    assert enriched["end_added"] is True
    assert enriched["start_relation_id"] == 200
    assert enriched["end_relation_id"] == 300
    assert enriched["geometry"][0] == [0.0, 0.0]
    assert enriched["geometry"][-1] == [3.0, 0.0]


def test_related_route_geometries_are_kept_separate(monkeypatch):
    line = SimpleNamespace(
        city="测试",
        name="3号线",
        stations=[
            _station("A站", 0.0, 0.0),
            _station("B站", 0.001, 0.0),
            _station("C站", 0.002, 0.0),
        ],
        geometry=[],
        _route_master_main_id=100,
        _route_master={
            "main": {
                "relation_id": 100,
                "records": [
                    {"name": "A站", "point": [0.0, 0.0]},
                    {"name": "B站", "point": [0.001, 0.0]},
                    {"name": "C站", "point": [0.002, 0.0]},
                ],
            },
            "branches": [
                {
                    "relation_id": 200,
                    "station_count": 2,
                    "records": [
                        {"name": "B站", "point": [0.001, 0.0]},
                        {"name": "D站", "point": [0.003, 0.0]},
                    ],
                    "metrics": {"orientation": "same"},
                }
            ],
            "partials": [
                {
                    "relation_id": 300,
                    "station_count": 2,
                    "records": [
                        {"name": "A站", "point": [0.0, 0.0]},
                        {"name": "B站", "point": [0.001, 0.0]},
                    ],
                    "metrics": {"overlap_ratio": 0.5},
                }
            ],
            "variants": [],
        },
    )

    main = _candidate(
        100,
        [
            {"id": 1, "name": "A站", "point": [0.0, 0.0]},
            {"id": 2, "name": "B站", "point": [0.001, 0.0]},
            {"id": 3, "name": "C站", "point": [0.002, 0.0]},
        ],
        [
            _way(101, [1, 2], [[0.0, 0.0], [0.001, 0.0]]),
            _way(102, [2, 3], [[0.001, 0.0], [0.002, 0.0]]),
        ],
        [101, 102],
        "测试3号线 主",
    )

    branch = _candidate(
        200,
        [
            {"id": 2, "name": "B站", "point": [0.001, 0.0]},
            {"id": 4, "name": "D站", "point": [0.003, 0.0]},
        ],
        [
            _way(201, [2, 4], [[0.001, 0.0], [0.003, 0.0]]),
        ],
        [201],
        "测试3号线 Branch",
    )

    partial = _candidate(
        300,
        [
            {"id": 1, "name": "A站", "point": [0.0, 0.0]},
            {"id": 2, "name": "B站", "point": [0.001, 0.0]},
        ],
        [
            _way(301, [1, 2], [[0.0, 0.0], [0.001, 0.0]]),
        ],
        [301],
        "测试3号线 Partial",
    )

    monkeypatch.setattr(
        route_builder,
        "get_line_relation_tracks",
        lambda *args, **kwargs: {
            "candidates": [main, branch, partial],
            "relations": [],
        },
    )

    result = route_builder.build_route_geometry(
        line,
        (0.0, 0.0, 0.01, 0.01),
    )

    assert result is line
    assert result.geometry
    assert result.geometry_relation_id == 100

    assert len(result.geometry_branches) == 1
    assert result.geometry_branches[0]["relation_id"] == 200
    assert result.geometry_branches[0]["role"] == "branches"
    assert result.geometry_branches[0]["start_station"] == "B站"
    assert result.geometry_branches[0]["end_station"] == "D站"
    assert result.geometry_branches[0]["projected_station_count"] == 2

    assert len(result.geometry_partials) == 1
    assert result.geometry_partials[0]["relation_id"] == 300
    assert result.geometry_partials[0]["role"] == "partials"
    assert result.geometry_partials[0]["projected_station_count"] == 2

    assert result.geometry_variants == []
