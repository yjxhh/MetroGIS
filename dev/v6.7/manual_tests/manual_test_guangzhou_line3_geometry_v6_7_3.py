"""V6.7-3 Guangzhou Line 3 real-data geometry integration test."""

from __future__ import annotations

import pytest

from metrogis.geometry.route_builder import (
    build_route_geometry,
    geometry_length,
    point_distance,
)
from metrogis.parser import route_builder as parser_route_builder


pytestmark = pytest.mark.integration


BBOX = (
    22.5607978,
    112.9523727,
    23.9356989,
    114.055299,
)


def _station_point(station):
    lat = getattr(station, "lat", None)
    lng = getattr(station, "lng", None)
    if lat is None or lng is None:
        return None
    return [float(lng), float(lat)]


def test_guangzhou_line3_v6_7_3_geometry_integration():
    print("\n" + "=" * 100)
    print("MetroGIS V6.7-3 广州 3 号线 Route Master -> Geometry 实战验收")
    print("=" * 100)
    print(f"BBox = {BBOX}")
    print("=" * 100)

    line = parser_route_builder.create_route(
        "广州",
        "3号线",
        BBOX,
    )

    assert line is not None
    names = [station.name for station in line.stations]
    master = getattr(line, "_route_master", None)

    assert master is not None
    assert names[0] == "机场北"
    assert names[-1] == "海傍"
    assert len(names) >= 28

    print("\nRoute Master")
    print("-" * 100)
    print(f"main relation = {master['main']['relation_id']}")
    print(f"station count = {len(names)}")
    print(f"start/end = {names[0]} -> {names[-1]}")
    print("-" * 100)

    line = build_route_geometry(
        line,
        BBOX,
    )

    geometry = getattr(line, "geometry", []) or []
    assert len(geometry) >= 2

    main_relation_id = master["main"]["relation_id"]
    geometry_relation_id = getattr(line, "geometry_relation_id", None)
    assert geometry_relation_id == main_relation_id
    assert getattr(line, "geometry_route_master_preferred", False) is True

    used_way_count = getattr(line, "geometry_used_way_count", 0)
    total_way_count = getattr(line, "geometry_total_way_count", 0)
    connected = getattr(line, "geometry_connected", False)
    projected_station_count = getattr(line, "geometry_projected_station_count", 0)
    max_snap = getattr(line, "geometry_max_snap", float("inf"))
    monotonic_failures = getattr(line, "geometry_station_monotonic_failures", -1)

    route_length = getattr(line, "geometry_length", 0.0)

    print("\nGeometry")
    print("-" * 100)
    print(f"relation id = {geometry_relation_id}")
    print(f"ways = {used_way_count}/{total_way_count}")
    print(f"connected = {connected}")
    print(f"geometry points = {len(geometry)}")
    print(f"projected stations = {projected_station_count}/{len(line.stations)}")
    print(f"max station snap = {max_snap:.2f} m")
    print(f"station monotonic failures = {monotonic_failures}")
    print(f"geometry length = {route_length / 1000:.3f} km")
    print(f"geometry start = {geometry[0]}")
    print(f"geometry end = {geometry[-1]}")
    print("-" * 100)

    assert used_way_count > 0
    assert total_way_count >= used_way_count
    assert connected is True
    assert projected_station_count == len(line.stations)
    assert monotonic_failures == 0
    assert max_snap < 100.0
    assert route_length > 1000.0
    assert abs(route_length - geometry_length(geometry)) < 1.0

    first_point = _station_point(line.stations[0])
    last_point = _station_point(line.stations[-1])
    assert first_point is not None
    assert last_point is not None

    start_distance = point_distance(first_point, geometry[0])
    end_distance = point_distance(last_point, geometry[-1])

    print(f"start endpoint distance = {start_distance:.2f} m")
    print(f"end endpoint distance = {end_distance:.2f} m")

    assert start_distance < 100.0
    assert end_distance < 100.0

    print("\n✅ Route Master Main Relation 被 Geometry 正确采用")
    print("✅ 28+ 站完整序列全部参与 Geometry 投影")
    print("✅ Relation Way chain 完整连续")
    print("✅ 首端机场北进入最终 Geometry")
    print("✅ 末端海傍进入最终 Geometry")
    print("✅ Geometry / Station 顺序检查通过")
    print("=" * 100)
