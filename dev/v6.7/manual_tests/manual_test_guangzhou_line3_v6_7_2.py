"""MetroGIS V6.7-2 real Overpass integration test: Guangzhou Line 3."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
V67_FILE = ROOT / "route_builder_V6_7_2.py"



def _load_v672():
    if not V67_FILE.exists():
        pytest.fail(f"Missing V6.7-2 reference file: {V67_FILE}")

    module_name = "metrogis_route_builder_v67_2_guangzhou_test"
    spec = importlib.util.spec_from_file_location(module_name, V67_FILE)
    if spec is None or spec.loader is None:
        pytest.fail("Unable to create V6.7-2 import spec")

    module = importlib.util.module_from_spec(spec)
    # Required by dataclasses on Python 3.14+ when loading a file directly.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_guangzhou_line3_route_master_resolution():
    rb = _load_v672()

    bbox = (
        22.5607978,
        112.9523727,
        23.9356989,
        114.055299,
    )

    print("\n")
    print("=" * 88)
    print("MetroGIS V6.7-2 广州 3 号线 Route Master 实战测试")
    print("=" * 88)
    print(f"BBox = {bbox}")
    print("=" * 88)

    line = rb.create_route("广州", "3号线", bbox)
    assert line is not None

    master = getattr(line, "_route_master", None)
    assert master is not None, "V6.7-2 没有生成 Route Master" 

    main = master.get("main") or {}
    main_pair = master.get("main_pair")
    branches = master.get("branches") or []
    partials = master.get("partials") or []
    variants = master.get("variants") or []
    cohort_ids = master.get("cohort_relation_ids") or []

    relation_id = getattr(line, "_relation_id", None)
    relation_name = getattr(line, "_relation_name", "")
    station_count = len(getattr(line, "stations", []) or [])

    print("\nRoute Master 摘要")
    print("-" * 88)
    print(f"master type       = {master.get('type')}")
    print(f"main relation     = {main.get('relation_id')}")
    print(f"main pair         = {main_pair}")
    print(f"branch count      = {len(branches)}")
    print(f"partial count     = {len(partials)}")
    print(f"variant count     = {len(variants)}")
    print(f"cohort relation   = {len(cohort_ids)}")
    print(f"selected relation = {relation_id}")
    print(f"selected name     = {relation_name}")
    print(f"selected stations = {station_count}")
    print("-" * 88)

    # 目前 Guangzhou OSM 数据应当能形成推断式 Route Master。
    assert master.get("type") in {"inferred_route_master", "osm_route_master"}
    assert main.get("relation_id") == relation_id
    assert relation_id is not None
    assert station_count >= 20

    # 主线必须有正反向 Relation 配对；Branch/Partial 至少各出现一种。
    assert main_pair is not None
    assert {main_pair.get("forward_id"), main_pair.get("reverse_id")} >= {relation_id} 
    assert branches, "没有识别出广州3号线 Branch Relation"
    assert partials, "没有识别出广州3号线 Partial/Short-turn Relation"

    # Route Master cohort 应只保留最高身份层，不能把低身份的邻近同号线路混进来。
    assert len(cohort_ids) < 30

    print("\n✅ Route Master 已生成")
    print("✅ Main 已确定")
    print("✅ Main 正反向 Relation 已配对")
    print("✅ Branch 已识别")
    print("✅ Partial/Short-turn 已识别")
    print("✅ 广州3号线进入 V6.7-2 主流程")
    print("=" * 88)


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", "-s", __file__]))
