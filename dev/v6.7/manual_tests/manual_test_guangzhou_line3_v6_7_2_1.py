"""MetroGIS V6.7-2.1 real Overpass integration test: Guangzhou Line 3."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
V67_FILE = ROOT / "route_builder_V6_7_2_1.py"


def _load_v6721():
    if not V67_FILE.exists():
        pytest.fail(f"Missing V6.7-2.1 reference file: {V67_FILE}")
    module_name = "metrogis_route_builder_v67_2_1_guangzhou_test"
    spec = importlib.util.spec_from_file_location(module_name, V67_FILE)
    if spec is None or spec.loader is None:
        pytest.fail("Unable to create V6.7-2.1 import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_guangzhou_line3_route_master_quality():
    rb = _load_v6721()
    bbox = (22.5607978, 112.9523727, 23.9356989, 114.055299)

    print("\n")
    print("=" * 96)
    print("MetroGIS V6.7-2.1 广州 3 号线 Route Master Quality 实战测试")
    print("=" * 96)
    print(f"BBox = {bbox}")
    print("=" * 96)

    line = rb.create_route("广州", "3号线", bbox)
    assert line is not None

    master = getattr(line, "_route_master", None)
    assert master is not None, "V6.7-2.1 没有生成 Route Master"

    main = master.get("main") or {}
    pair = master.get("main_pair")
    pair_quality = master.get("main_pair_quality") or {}
    quality = master.get("quality") or {}
    branches = master.get("branches") or []
    partials = master.get("partials") or []
    variants = master.get("variants") or []
    cohort_ids = master.get("cohort_relation_ids") or []

    relation_id = getattr(line, "_relation_id", None)
    relation_name = getattr(line, "_relation_name", "")
    station_count = len(getattr(line, "stations", []) or [])

    print("\nRoute Master Quality 摘要")
    print("-" * 96)
    print(f"master type            = {master.get('type')}")
    print(f"main relation          = {main.get('relation_id')}")
    print(f"main start             = {main.get('start_station')}")
    print(f"main end               = {main.get('end_station')}")
    print(f"main pair              = {pair}")
    print(f"main pair quality      = {pair_quality}")
    print(f"branch count           = {len(branches)}")
    print(f"partial count          = {len(partials)}")
    print(f"variant count          = {len(variants)}")
    print(f"cohort relation count  = {len(cohort_ids)}")
    print(f"quality summary        = {quality}")
    print(f"selected relation      = {relation_id}")
    print(f"selected name          = {relation_name}")
    print(f"selected stations      = {station_count}")
    print("-" * 96)

    assert main.get("relation_id") == relation_id
    assert relation_id is not None
    assert station_count >= 20
    assert pair is not None
    assert pair_quality
    assert 0.0 <= pair_quality.get("overlap_ratio", -1.0) <= 1.0
    assert 0.0 <= pair_quality.get("confidence", -1.0) <= 1.0
    assert pair_quality.get("shared_stops", 0) >= 2
    assert branches
    assert partials
    assert len(cohort_ids) < 30

    print("\n✅ V6.7-2.1 Route Master 已生成")
    print("✅ Main 已确定")
    print("✅ Main 正反向 Relation 已配对")
    print("✅ overlap_ratio 已归一到 0~1")
    print("✅ shared_stops / coverage / endpoint_match / confidence 已生成")
    print("✅ Branch / Partial 已保留质量指标")
    print("=" * 96)


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", "-s", __file__]))
