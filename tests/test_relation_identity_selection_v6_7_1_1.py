"""MetroGIS V6.7-1.1 Relation Identity regression tests.

These tests intentionally load the canonical root-level route_builder_V6_7.py
instead of importing metrogis.parser.route_builder, so the tested artifact is the
file that is distributed as the V6.7-1.1 reference implementation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parent
V67_FILE = ROOT.parent / "route_builder_V6_7.py"


def _load_v67_module():
    if not V67_FILE.exists():
        pytest.fail(f"Missing V6.7 reference file: {V67_FILE}")

    module_name = "metrogis_route_builder_v67_1_1_test"
    spec = importlib.util.spec_from_file_location(module_name, V67_FILE)
    if spec is None or spec.loader is None:
        pytest.fail("Unable to create V6.7-1.1 import spec")

    module = importlib.util.module_from_spec(spec)
    # Required by dataclasses on Python 3.14+ when importing from a file path.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _candidate(relation_id, identity_score, ref, name, names):
    node_ids = [relation_id * 1000 + i for i in range(len(names))]
    return {
        "relation": {
            "id": relation_id,
            "tags": {
                "ref": ref,
                "name": name,
            },
            "_score": identity_score,
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
                "name": stop_name,
            }
            for index, (node_id, stop_name) in enumerate(zip(node_ids, names))
        },
    }


def test_line_identity_key_extracts_exact_codes():
    rb = _load_v67_module()

    assert rb._line_identity_key("3号线") == "3"
    assert rb._line_identity_key("11号线") == "11"
    assert rb._line_identity_key("地铁 13号线") == "13"
    assert rb._line_identity_key("F3") == "f3"
    assert rb._line_identity_key("APM") == "apm"
    assert rb._line_identity_key("地铁广佛线") == "广佛线"


def test_relation_identity_rejects_numeric_substring_collisions():
    rb = _load_v67_module()

    assert rb._relation_identity_matches(
        "3号线",
        _candidate(1, 90, "3", "地铁 3号线：A → B", ["A", "B"]),
    )
    assert not rb._relation_identity_matches(
        "3号线",
        _candidate(2, 999, "13", "地铁 13号线：A → B", ["A", "B"]),
    )
    assert rb._relation_identity_matches(
        "11号线",
        _candidate(3, 90, "11", "地铁 11号线：A → B", ["A", "B"]),
    )
    assert not rb._relation_identity_matches(
        "11号线",
        _candidate(4, 999, "111", "地铁 111号线：A → B", ["A", "B"]),
    )


def test_relation_identity_distinguishes_foshan_f3_from_guangzhou_3():
    rb = _load_v67_module()

    f3 = _candidate(
        5,
        70,
        "F3",
        "地铁 3号线：顺德学院站 → 佛山大学",
        ["顺德学院站", "佛山大学"],
    )

    assert rb._relation_identity_matches("F3", f3)
    assert not rb._relation_identity_matches("3号线", f3)


def test_relation_selection_filters_wrong_identity_before_score(monkeypatch):
    rb = _load_v67_module()

    wrong_13 = _candidate(
        10,
        999,
        "13",
        "地铁 13号线：天河公园 → 新沙",
        ["A", "B", "C"],
    )
    right_3 = _candidate(
        20,
        90,
        "3",
        "地铁 3号线：机场北 → 海傍",
        ["D", "E", "F"],
    )

    monkeypatch.setattr(
        rb,
        "_call_relation_tracks",
        lambda *args, **kwargs: {
            "candidates": [wrong_13, right_3],
        },
    )

    result = rb._discover_stations_from_relation(
        "广州",
        "3号线",
        (),
        [],
    )

    assert result is not None
    assert result["relation_id"] == 20
    assert result["identity_score"] == 90
    assert [station["name"] for station in result["stations"]] == ["D", "E", "F"]
