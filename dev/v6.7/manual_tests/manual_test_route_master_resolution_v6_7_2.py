"""MetroGIS V6.7-2 Route Master / Main / Branch / Partial tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parent
V67_FILE = ROOT / "route_builder_V6_7_2.py"


def _install_import_stubs(monkeypatch):
    """Load the root reference file without requiring the full MetroGIS app."""
    metrogis = types.ModuleType("metrogis")
    api = types.ModuleType("metrogis.api")
    parser = types.ModuleType("metrogis.parser")
    resources = types.ModuleType("metrogis.resources")
    api_overpass = types.ModuleType("metrogis.api.overpass")
    api_station = types.ModuleType("metrogis.api.station")
    parser_matcher = types.ModuleType("metrogis.parser.station_matcher")
    resources_loader = types.ModuleType("metrogis.resources.loader")

    api_overpass.get_line_relation_tracks = lambda *args, **kwargs: {}
    api_station.get_line_stations = lambda *args, **kwargs: []
    parser_matcher.station_name_score = lambda a, b: 100.0 if str(a).strip() == str(b).strip() else 0.0
    resources_loader.get_station_list = lambda *args, **kwargs: []

    metrogis.__path__ = []
    api.__path__ = []
    parser.__path__ = []
    resources.__path__ = []
    monkeypatch.setitem(sys.modules, "metrogis", metrogis)
    monkeypatch.setitem(sys.modules, "metrogis.api", api)
    monkeypatch.setitem(sys.modules, "metrogis.parser", parser)
    monkeypatch.setitem(sys.modules, "metrogis.resources", resources)
    monkeypatch.setitem(sys.modules, "metrogis.api.overpass", api_overpass)
    monkeypatch.setitem(sys.modules, "metrogis.api.station", api_station)
    monkeypatch.setitem(sys.modules, "metrogis.parser.station_matcher", parser_matcher)
    monkeypatch.setitem(sys.modules, "metrogis.resources.loader", resources_loader)


def _load_v672(monkeypatch):
    _install_import_stubs(monkeypatch)

    if not V67_FILE.exists():
        pytest.fail(f"Missing V6.7-2 reference file: {V67_FILE}")

    module_name = "metrogis_route_builder_v67_2_test"
    spec = importlib.util.spec_from_file_location(module_name, V67_FILE)
    if spec is None or spec.loader is None:
        pytest.fail("Unable to create V6.7-2 import spec")

    module = importlib.util.module_from_spec(spec)
    # Required by dataclasses on Python 3.14+ when importing from a file path.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _candidate(relation_id, score, ref, name, station_names):
    node_ids = [relation_id * 1000 + i for i in range(len(station_names))]
    return {
        "relation": {
            "id": relation_id,
            "tags": {
                "type": "route",
                "route": "subway",
                "ref": ref,
                "name": name,
            },
            "_score": score,
        },
        "stops": [
            {"ref": node_id, "role": "stop", "index": index}
            for index, node_id in enumerate(node_ids)
        ],
        "stop_nodes": {
            node_id: {
                "id": node_id,
                "lat": 23.0 + index * 0.001,
                "lng": 113.0 + index * 0.001,
                "name": station_name,
            }
            for index, (node_id, station_name) in enumerate(zip(node_ids, station_names))
        },
    }


def _fixture_candidates():
    main_forward = ["机场北", "高增", "人和", "龙归", "嘉禾望岗", "白云大道北", "永泰", "同和", "体育西路", "珠江新城", "广州塔", "客村"]
    main_reverse = list(reversed(main_forward))

    branch_forward = ["天河客运站", "五山", "华师", "体育西路", "珠江新城", "广州塔", "客村", "大塘", "沥滘"]
    branch_reverse = list(reversed(branch_forward))

    partial_forward = ["嘉禾望岗", "白云大道北", "永泰", "同和", "体育西路", "珠江新城"]

    wrong_same_ref = ["A城站1", "A城站2", "A城站3", "A城站4", "A城站5"]
    line13 = ["13号站1", "13号站2", "13号站3", "13号站4"]

    return [
        _candidate(100, 90, "3", "地铁 3号线：机场北 → 珠江新城", main_forward),
        _candidate(101, 90, "3", "地铁 3号线：珠江新城 → 机场北", main_reverse),
        _candidate(102, 90, "3", "地铁 3号线：天河客运站 → 客村", branch_forward),
        _candidate(103, 90, "3", "地铁 3号线：客村 → 天河客运站", branch_reverse),
        _candidate(104, 90, "3", "地铁 3号线：嘉禾望岗 → 珠江新城", partial_forward),
        _candidate(105, 70, "3", "华为松山湖有轨电车3号线", wrong_same_ref),
        _candidate(106, 90, "13", "地铁 13号线：鱼珠 → 新沙", line13),
    ]


def test_route_master_identifies_main_direction_pair_branch_and_partial(monkeypatch):
    rb = _load_v672(monkeypatch)

    candidates = _fixture_candidates()
    evaluated = []

    for candidate in candidates:
        if not rb._relation_identity_matches("3号线", candidate):
            continue

        records = rb._candidate_records(candidate)
        oriented, reversed_relation, matched_count, matched_score = rb._orient_relation([], records)
        evaluated.append(
            {
                "candidate": candidate,
                "records": oriented,
                "reverse": reversed_relation,
                "matched_count": matched_count,
                "matched_score": matched_score,
                "coverage": 0.0,
                "identity_score": rb._candidate_identity_score(candidate),
                "station_count": len(oriented),
                "relation_id": candidate["relation"]["id"],
                "relation_name": rb._relation_candidate_label(candidate),
                "line_name": "3号线",
                "metadata": rb._candidate_metadata(candidate),
            }
        )

    # 13号线 must be removed by exact identity before Route Master inference.
    assert 106 not in [item["relation_id"] for item in evaluated]

    master = rb._resolve_route_master(evaluated, [])
    assert master is not None

    assert master["type"] == "inferred_route_master"
    assert master["main"]["relation_id"] == 100

    assert master["main_pair"] is not None
    assert {master["main_pair"]["forward_id"], master["main_pair"]["reverse_id"]} == {100, 101}

    assert 102 in [item["relation_id"] for item in master["branches"]]
    assert 103 in [item["relation_id"] for item in master["branches"]]
    assert 104 in [item["relation_id"] for item in master["partials"]]

    # Same-ref but lower identity tier is outside the Route Master cohort.
    assert 105 not in master["cohort_relation_ids"]


def test_route_master_prefers_longest_main_when_no_official_yaml(monkeypatch):
    rb = _load_v672(monkeypatch)

    candidates = [
        _candidate(200, 90, "3", "地铁 3号线：短线", ["A", "B", "C", "D"]),
        _candidate(201, 90, "3", "地铁 3号线：主线", ["A", "B", "C", "D", "E", "F", "G", "H"]),
    ]

    evaluated = []
    for candidate in candidates:
        records = rb._candidate_records(candidate)
        evaluated.append(
            {
                "candidate": candidate,
                "records": records,
                "reverse": False,
                "matched_count": 0,
                "matched_score": 0.0,
                "coverage": 0.0,
                "identity_score": rb._candidate_identity_score(candidate),
                "station_count": len(records),
                "relation_id": candidate["relation"]["id"],
                "relation_name": rb._relation_candidate_label(candidate),
                "line_name": "3号线",
                "metadata": rb._candidate_metadata(candidate),
            }
        )

    master = rb._resolve_route_master(evaluated, [])
    assert master is not None
    assert master["main"]["relation_id"] == 201
    assert master["main"]["station_count"] == 8


def test_discover_uses_route_master_and_stores_main_metadata(monkeypatch):
    rb = _load_v672(monkeypatch)

    candidates = _fixture_candidates()
    monkeypatch.setattr(
        rb,
        "_call_relation_tracks",
        lambda city_name, line_name, bbox: {"candidates": candidates},
    )

    result = rb._discover_stations_from_relation(
        "广州",
        "3号线",
        (22.0, 112.0, 24.0, 114.5),
        [],
    )

    assert result is not None
    assert result["relation_id"] == 100
    assert result["route_master"]["main"]["relation_id"] == 100
    assert {result["route_master"]["main_pair"]["forward_id"], result["route_master"]["main_pair"]["reverse_id"]} == {100, 101}
    assert 102 in [item["relation_id"] for item in result["route_master"]["branches"]]
    assert 104 in [item["relation_id"] for item in result["route_master"]["partials"]]


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", "-s", __file__]))
