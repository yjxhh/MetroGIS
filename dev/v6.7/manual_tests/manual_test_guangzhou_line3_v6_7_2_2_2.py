"""MetroGIS V6.7-2.2 Guangzhou Line 3 endpoint-completion integration test."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


BBOX = (
    22.5607978,
    112.9523727,
    23.9356989,
    114.055299,
)


def _station_names(line):
    names = []
    for station in getattr(line, "stations", []) or []:
        name = getattr(station, "name", None)
        if not name and isinstance(station, dict):
            name = station.get("name")
        if name:
            names.append(str(name).strip())
    return names


def test_guangzhou_line3_v6_7_2_2():
    from metrogis.parser import route_builder as rb

    print("\n" + "=" * 96)
    print("MetroGIS V6.7-2.2.2 广州 3 号线 Route Master Station Completion 实战测试")
    print("=" * 96)
    print(f"BBox = {BBOX}")
    print("=" * 96)

    line = rb.create_route(
        "广州",
        "3号线",
        BBOX,
    )

    assert line is not None

    names = _station_names(line)
    master = getattr(line, "_route_master", None)
    assert master is not None

    main = master.get("main", {})
    completion = master.get("completion", {}) or {}
    main_completion = main.get("completion", {}) or {}

    print("\nRoute Master Completion 摘要")
    print("-" * 96)
    print(f"main relation          = {main.get('relation_id')}")
    print(f"declared start         = {main.get('declared_start_station')}")
    print(f"declared end           = {main.get('declared_end_station')}")
    print(f"actual start           = {main.get('start_station')}")
    print(f"actual end             = {main.get('end_station')}")
    print(f"main station count     = {main.get('station_count')}")
    print(f"completion applied     = {completion.get('applied')}")
    print(f"unique added stops     = {completion.get('unique_added_stops')}" )
    print(f"forward added stops    = {completion.get('forward_added_stops')}" )
    print(f"reverse added stops    = {completion.get('reverse_added_stops')}" )
    print(f"directional added      = {completion.get('directional_added_stops')}" )
    print(f"legacy total_added     = {completion.get('total_added_stops')}" )
    print(f"completion confidence  = {completion.get('confidence')}")
    print(f"main first stations    = {names[:5]}")
    print(f"main last stations     = {names[-5:]}")
    print("-" * 96)

    # Current Guangzhou Line 3 evidence used by the test:
    # the active long-form Relation declares Airport North -> Haibang but the
    # Relation stop sequence observed by the parser starts at Gaozeng and ends
    # at Haichong Lu. V6.7-2.2.2 should recover both terminals from same-cohort
    # evidence Relations rather than inventing them.
    assert main.get("declared_start_station") == "机场北"
    assert main.get("declared_end_station") == "海傍"
    assert main.get("start_station") == "机场北"
    assert main.get("end_station") == "海傍"
    assert main.get("station_count") >= 28

    assert main_completion.get("added_start_count", 0) >= 1
    assert main_completion.get("added_end_count", 0) >= 1
    assert main_completion.get("confidence", 0.0) > 0.70

    # V6.7-2.2.2: report canonical/net additions separately from the
    # directional additions of forward and reverse Main Relations.
    assert completion.get("unique_added_stops") == 2
    assert completion.get("forward_added_stops") == 2
    assert completion.get("reverse_added_stops") == 2
    assert completion.get("directional_added_stops") == 4
    assert completion.get("total_added_stops") == 2

    assert names[0] == "机场北"
    assert names[-1] == "海傍"

    print("\n✅ Main Relation 缺失首端已补齐")
    print("✅ Main Relation 缺失末端已补齐")
    print("✅ Main Station Sequence 已升级为完整端点序列")
    print("✅ V6.7-2.2.2 Route Master Station Completion 生效")
    print("=" * 96)
