"""MetroGIS V6.7-2.2 Route Master endpoint-completion regression tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
V6722_FILE = ROOT / "route_builder_V6_7_2_2.py"


def _load_module():
    if not V6722_FILE.exists():
        pytest.fail(f"Missing V6.7-2.2 reference file: {V6722_FILE}")

    # The repository snapshot used for offline regression may contain an older
    # overpass.py without the V6.7 Relation API symbol. The completion tests do
    # not perform network calls, so provide a harmless compatibility symbol.
    from metrogis.api import overpass
    if not hasattr(overpass, "get_line_relation_tracks"):
        overpass.get_line_relation_tracks = lambda *args, **kwargs: {"candidates": []}

    import types
    if "metrogis.api.station" not in sys.modules:
        station_api = types.ModuleType("metrogis.api.station")
        station_api.get_line_stations = lambda *args, **kwargs: []
        sys.modules["metrogis.api.station"] = station_api

    if "metrogis.parser.station_matcher" not in sys.modules:
        matcher = types.ModuleType("metrogis.parser.station_matcher")
        matcher.station_name_score = lambda a, b: 100.0 if str(a).strip() == str(b).strip() else 0.0
        sys.modules["metrogis.parser.station_matcher"] = matcher

    if "metrogis.resources.loader" not in sys.modules:
        loader = types.ModuleType("metrogis.resources.loader")
        loader.get_station_list = lambda *args, **kwargs: []
        sys.modules["metrogis.resources.loader"] = loader

    module_name = "metrogis_route_builder_v67_2_2_test"
    spec = importlib.util.spec_from_file_location(module_name, V6722_FILE)
    if spec is None or spec.loader is None:
        pytest.fail("Unable to create V6.7-2.2 import spec")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _records(names: list[str], start_lon: float = 113.0) -> list[dict]:
    return [
        {
            "id": index + 1,
            "name": name,
            "point": (start_lon + index * 0.01, 23.0 + index * 0.01),
            "raw": None,
        }
        for index, name in enumerate(names)
    ]


def _evaluated(
    relation_id: int,
    name: str,
    names: list[str],
    identity: float = 90.0,
) -> dict:
    module = _load_module()
    # Reuse the production metadata parser so the test covers the same endpoint
    # hint path as a real Relation name.
    candidate = {
        "relation": {
            "id": relation_id,
            "tags": {
                "ref": "3",
                "name": name,
            },
            "_score": identity,
        }
    }
    metadata = module._candidate_metadata(candidate)
    return {
        "candidate": candidate,
        "records": _records(names),
        "reverse": False,
        "matched_count": 0,
        "matched_score": 0.0,
        "coverage": 0.0,
        "identity_score": identity,
        "station_count": len(names),
        "relation_id": relation_id,
        "relation_name": name,
        "line_name": "3号线",
        "metadata": metadata,
    }


def test_main_endpoint_completion_uses_same_cohort_evidence():
    rb = _load_module()

    main = _evaluated(
        100,
        "地铁 3号线：A → E",
        ["B", "C", "D"],
    )
    reverse = _evaluated(
        101,
        "地铁 3号线：E → A",
        ["D", "C", "B"],
    )
    start_evidence = _evaluated(
        102,
        "地铁 3号线：A → B",
        ["A", "B"],
    )
    end_evidence = _evaluated(
        103,
        "地铁 3号线：D → E",
        ["D", "E"],
    )

    master = rb._resolve_route_master(
        [main, reverse, start_evidence, end_evidence],
        [],
    )

    assert master is not None
    assert master["main"]["relation_id"] == 100
    assert [r["name"] for r in master["main"]["records"]] == ["A", "B", "C", "D", "E"]

    completion = master["main"]["completion"]
    assert completion["applied"] is True
    assert completion["added_start_count"] == 1
    assert completion["added_end_count"] == 1
    assert completion["added_count"] == 2
    assert completion["actual_start_after"] == "A"
    assert completion["actual_end_after"] == "E"


def test_endpoint_completion_does_not_invent_missing_terminal():
    rb = _load_module()

    main = _evaluated(
        200,
        "地铁 3号线：A → E",
        ["B", "C", "D"],
    )
    unrelated = _evaluated(
        201,
        "地铁 3号线：X → Y",
        ["X", "Y"],
    )

    completed, info = rb._complete_main_route_endpoints(
        main,
        [main, unrelated],
    )

    assert [r["name"] for r in completed["records"]] == ["B", "C", "D"]
    assert info["applied"] is False
    assert info["added_count"] == 0


def test_main_pair_quality_is_recomputed_after_completion():
    rb = _load_module()

    main = _evaluated(
        300,
        "地铁 3号线：A → E",
        ["B", "C", "D"],
    )
    reverse = _evaluated(
        301,
        "地铁 3号线：E → A",
        ["D", "C", "B"],
    )
    start_evidence = _evaluated(
        302,
        "地铁 3号线：A → B",
        ["A", "B"],
    )
    end_evidence = _evaluated(
        303,
        "地铁 3号线：D → E",
        ["D", "E"],
    )

    master = rb._resolve_route_master(
        [main, reverse, start_evidence, end_evidence],
        [],
    )

    quality = master["main_pair_quality"]
    assert quality is not None
    assert quality["shared_stops"] == 5
    assert quality["overlap_ratio"] == 1.0
    assert quality["forward_coverage"] == 1.0
    assert quality["reverse_coverage"] == 1.0
    assert quality["endpoint_match"] is True
    assert quality["confidence"] == 1.0


def test_declared_endpoint_metadata_prefers_from_to_over_relation_name():
    rb = _load_module()

    candidate = {
        "relation": {
            "id": 400,
            "tags": {
                "ref": "3",
                "name": "地铁 3号线：A → B",
                "from": "X",
                "to": "Y",
            },
        }
    }

    item = {
        "relation_id": 400,
        "relation_name": "地铁 3号线：A → B",
        "metadata": rb._candidate_metadata(candidate),
    }

    assert rb._candidate_endpoint_hints(item) == ("X", "Y")
