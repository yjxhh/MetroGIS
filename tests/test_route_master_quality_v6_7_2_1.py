"""MetroGIS V6.7-2.1 Route Master quality regression tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parent
V67_FILE = ROOT / "route_builder_V6_7_2_1.py"


def _install_import_stubs(monkeypatch):
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
    parser_matcher.station_name_score = (
        lambda a, b: 100.0 if str(a).strip() == str(b).strip() else 0.0
    )
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


def _load_v6721(monkeypatch):
    _install_import_stubs(monkeypatch)
    if not V67_FILE.exists():
        pytest.fail(f"Missing V6.7-2.1 reference file: {V67_FILE}")
    module_name = "metrogis_route_builder_v67_2_1_quality_test"
    spec = importlib.util.spec_from_file_location(module_name, V67_FILE)
    if spec is None or spec.loader is None:
        pytest.fail("Unable to create V6.7-2.1 import spec")
    module = importlib.util.module_from_spec(spec)
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
    main = ["机场北", "高增", "人和", "龙归", "嘉禾望岗", "白云大道北", "永泰", "同和", "体育西路", "珠江新城", "广州塔", "客村"]
    branch = ["天河客运站", "五山", "华师", "体育西路", "珠江新城", "广州塔", "客村", "大塘", "沥滘"]
    partial = ["嘉禾望岗", "白云大道北", "永泰", "同和", "体育西路", "珠江新城"]
    wrong_same_ref = ["A城站1", "A城站2", "A城站3", "A城站4", "A城站5"]
    line13 = ["13号站1", "13号站2", "13号站3", "13号站4"]
    return [
        _candidate(100, 90, "3", "地铁 3号线：机场北 → 珠江新城", main),
        _candidate(101, 90, "3", "地铁 3号线：珠江新城 → 机场北", list(reversed(main))),
        _candidate(102, 90, "3", "地铁 3号线：天河客运站 → 客村", branch),
        _candidate(103, 90, "3", "地铁 3号线：客村 → 天河客运站", list(reversed(branch))),
        _candidate(104, 90, "3", "地铁 3号线：嘉禾望岗 → 珠江新城", partial),
        _candidate(105, 70, "3", "华为松山湖有轨电车3号线", wrong_same_ref),
        _candidate(106, 90, "13", "地铁 13号线：鱼珠 → 新沙", line13),
    ]


def _evaluate(rb, candidate):
    records = rb._candidate_records(candidate)
    return {
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


def test_overlap_metrics_are_normalized(monkeypatch):
    rb = _load_v6721(monkeypatch)
    a = [{"name": n} for n in ["A", "B", "C", "D"]]
    b = [{"name": n} for n in ["D", "C", "B", "A"]]
    metrics = rb._sequence_overlap_metrics(a, list(reversed(b)))
    assert metrics["shared_stops"] == 4
    assert metrics["overlap_ratio"] == 1.0
    assert 0.0 <= metrics["overlap_ratio"] <= 1.0
    assert 0.0 <= metrics["a_coverage"] <= 1.0
    assert 0.0 <= metrics["b_coverage"] <= 1.0


def test_main_pair_quality_has_no_bonus_overflow(monkeypatch):
    rb = _load_v6721(monkeypatch)
    evaluated = [_evaluate(rb, c) for c in _fixture_candidates() if rb._relation_identity_matches("3号线", c)]
    master = rb._resolve_route_master(evaluated, [])
    assert master is not None
    pair = master["main_pair"]
    assert pair is not None
    assert pair["shared_stops"] == 12
    assert pair["overlap_ratio"] == 1.0
    assert pair["overlap"] == 1.0
    assert pair["forward_coverage"] == 1.0
    assert pair["reverse_coverage"] == 1.0
    assert pair["endpoint_match"] is True
    assert pair["confidence"] == 1.0
    quality = master["main_pair_quality"]
    assert quality["overlap_ratio"] == 1.0
    assert quality["confidence"] == 1.0

    assert 102 in [item["relation_id"] for item in master["branches"]]
    assert 103 in [item["relation_id"] for item in master["branches"]]
    assert 104 in [item["relation_id"] for item in master["partials"]]


def test_classification_metrics_are_bounded_and_exposed(monkeypatch):
    rb = _load_v6721(monkeypatch)
    evaluated = [_evaluate(rb, c) for c in _fixture_candidates() if rb._relation_identity_matches("3号线", c)]
    master = rb._resolve_route_master(evaluated, [])
    assert master is not None
    for group in (master["branches"], master["partials"], master["variants"]):
        for item in group:
            metrics = item["metrics"]
            for key in ("item_coverage", "main_coverage", "overlap_ratio", "reverse_overlap_ratio", "direct_overlap_ratio"):
                assert 0.0 <= metrics[key] <= 1.0
            assert metrics["shared_stops"] >= 0
            assert metrics["exclusive_stops"] >= 0


def test_route_master_quality_summary_and_excluded_ids(monkeypatch):
    rb = _load_v6721(monkeypatch)
    evaluated = [_evaluate(rb, c) for c in _fixture_candidates() if rb._relation_identity_matches("3号线", c)]
    master = rb._resolve_route_master(evaluated, [])
    assert master is not None
    assert 105 in master["excluded_relation_ids"]
    assert master["quality"]["cohort_size"] == 5
    assert master["quality"]["candidate_size"] == 6
    assert master["quality"]["branch_count"] == len(master["branches"])
    assert master["quality"]["partial_count"] == len(master["partials"])
    assert 0.0 <= master["quality"]["main_pair_confidence"] <= 1.0
