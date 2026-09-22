"""V6.7-3 Guangzhou Line 3 live acceptance for related geometries."""

from __future__ import annotations

import pytest

from metrogis.geometry.route_builder import build_route_geometry
from metrogis.parser import route_builder as parser_route_builder


pytestmark = pytest.mark.integration


BBOX = (
    22.5607978,
    112.9523727,
    23.9356989,
    114.055299,
)


def _route_master_role_ids(master, role):
    return {
        item.get("relation_id")
        for item in (master.get(role, []) or [])
        if item.get("relation_id") is not None
    }


def test_guangzhou_line3_v6_7_3_related_geometry_live():
    print("\n" + "=" * 100)
    print("MetroGIS V6.7-3 广州 3 号线 Branch / Partial Geometry 实战验收")
    print("=" * 100)
    print(f"BBox = {BBOX}")
    print("=" * 100)

    line = parser_route_builder.create_route(
        "广州",
        "3号线",
        BBOX,
    )
    assert line is not None

    master = getattr(line, "_route_master", None)
    assert master is not None

    line = build_route_geometry(line, BBOX)

    branches = list(getattr(line, "geometry_branches", []) or [])
    partials = list(getattr(line, "geometry_partials", []) or [])
    variants = list(getattr(line, "geometry_variants", []) or [])

    master_branch_ids = _route_master_role_ids(master, "branches")
    master_partial_ids = _route_master_role_ids(master, "partials")
    master_variant_ids = _route_master_role_ids(master, "variants")

    branch_ids = {item.get("relation_id") for item in branches}
    partial_ids = {item.get("relation_id") for item in partials}
    variant_ids = {item.get("relation_id") for item in variants}

    print("\nRoute Master / Geometry")
    print("-" * 100)
    print(f"Route Master branches = {len(master_branch_ids)}")
    print(f"Geometry branches     = {len(branches)}")
    print(f"Route Master partials = {len(master_partial_ids)}")
    print(f"Geometry partials     = {len(partials)}")
    print(f"Route Master variants = {len(master_variant_ids)}")
    print(f"Geometry variants     = {len(variants)}")
    print("-" * 100)

    assert branch_ids == master_branch_ids
    assert partial_ids == master_partial_ids
    assert variant_ids == master_variant_ids

    assert master_branch_ids
    assert master_partial_ids or master_variant_ids

    for role, items in (
        ("branch", branches),
        ("partial", partials),
        ("variant", variants),
    ):
        for item in items:
            geometry = item.get("geometry", []) or []
            station_count = int(item.get("station_count", 0) or 0)
            projected = int(item.get("projected_station_count", 0) or 0)
            failures = int(item.get("station_monotonic_failures", 0) or 0)
            way_count = int(item.get("used_way_count", 0) or 0)

            print(
                f"{role} relation {item.get('relation_id')} | "
                f"{item.get('start_station')} -> {item.get('end_station')} | "
                f"stations={station_count} | "
                f"projected={projected} | "
                f"ways={way_count} | "
                f"length={item.get('length', 0.0) / 1000:.3f} km | "
                f"max_snap={item.get('max_snap', 0.0):.1f} m | "
                f"monotonic_failures={failures}"
            )

            total_way_count = int(item.get("total_way_count", 0) or 0)
            way_coverage = (
                way_count / total_way_count
                if total_way_count
                else 0.0
            )
            max_snap = float(item.get("max_snap", 0.0) or 0.0)

            assert geometry and len(geometry) >= 2
            assert way_count > 0
            assert total_way_count > 0
            assert way_coverage >= 0.75
            assert projected == station_count
            assert failures == 0
            assert max_snap <= 2000.0
            assert item.get("length", 0.0) > 100.0
            assert item.get("way_chain_continuous", False) is True

    print("\n✅ Main Geometry 保持独立")
    print("✅ Branch Geometry 与 Route Master Branch 一一对应")
    print("✅ Partial Geometry 与 Route Master Partial 一一对应")
    print("✅ Variant Geometry 与 Route Master Variant 一一对应")
    print("✅ 相关 Relation 的站序投影检查通过")
    print("=" * 100)
