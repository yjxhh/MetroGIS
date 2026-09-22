from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 1. 精确线路身份测试
# ---------------------------------------------------------------------------

def test_line3_does_not_match_line13():
    from metrogis.parser import route_builder as rb

    line3 = {
        "relation": {
            "tags": {
                "ref": "3",
                "name": "地铁 3号线：天河客运站 → 海傍",
            }
        }
    }

    line13 = {
        "relation": {
            "tags": {
                "ref": "13",
                "name": "地铁 13号线：鱼珠 → 新沙",
            }
        }
    }

    assert rb._relation_identity_matches("3号线", line3)
    assert not rb._relation_identity_matches("3号线", line13)


def test_line3_does_not_match_foshan_f3():
    from metrogis.parser import route_builder as rb

    guangzhou_3 = {
        "relation": {
            "tags": {
                "ref": "3",
                "name": "地铁 3号线",
            }
        }
    }

    foshan_f3 = {
        "relation": {
            "tags": {
                "ref": "F3",
                "name": "佛山地铁 F3",
            }
        }
    }

    assert rb._relation_identity_matches("3号线", guangzhou_3)
    assert not rb._relation_identity_matches("3号线", foshan_f3)


# ---------------------------------------------------------------------------
# 2. 广州 3 号线真实 Relation 测试
# ---------------------------------------------------------------------------

def test_guangzhou_line3_real_overpass():
    from metrogis.parser import route_builder as rb

    # 广州 3 号线覆盖范围
    bbox = (
        22.5607978,
        112.9523727,
        23.9356989,
        114.055299,
    )

    city = "广州"
    line_name = "3号线"

    print("\n")
    print("=" * 80)
    print("MetroGIS V6.7-1.1 广州 3 号线真实测试")
    print("=" * 80)
    print(f"城市: {city}")
    print(f"线路: {line_name}")
    print(f"BBox: {bbox}")
    print("=" * 80)

    # 直接调用当前安装到 metrogis/parser 的 V6.7.1.1
    line = rb.create_route(
        city,
        line_name,
        bbox,
    )

    assert line is not None

    # ---------------------------------------------------------------
    # 打印 Relation 选择结果
    # ---------------------------------------------------------------

    relation_id = getattr(line, "_relation_id", None)
    relation_name = getattr(line, "_relation_name", None)
    identity_score = getattr(line, "_relation_identity_score", None)
    station_source = getattr(line, "_station_source", None)
    station_count = len(getattr(line, "stations", []) or [])
    inserted_count = getattr(line, "_relation_station_inserted", None)
    matched_count = getattr(line, "_relation_station_match_count", None)
    coverage = getattr(line, "_relation_station_coverage", None)
    reversed_relation = getattr(line, "_relation_reversed", None)

    print("\n")
    print("-" * 80)
    print("最终 Relation")
    print("-" * 80)
    print(f"relation_id       = {relation_id}")
    print(f"relation_name     = {relation_name}")
    print(f"identity_score    = {identity_score}")
    print(f"station_source    = {station_source}")
    print(f"station_count     = {station_count}")
    print(f"matched_count     = {matched_count}")
    print(f"inserted_count    = {inserted_count}")
    print(f"coverage          = {coverage}")
    print(f"reversed          = {reversed_relation}")
    print("-" * 80)

    # ---------------------------------------------------------------
    # 站点打印
    # ---------------------------------------------------------------

    stations = getattr(line, "stations", []) or []

    names = []

    for index, station in enumerate(stations, start=1):
        name = getattr(station, "name", None)

        if not name and isinstance(station, dict):
            name = station.get("name")

        name = str(name or "").strip()

        names.append(name)

        print(f"{index:02d}. {name}")

    print("-" * 80)
    print(f"最终站点总数: {len(names)}")
    print("-" * 80)

    # ---------------------------------------------------------------
    # 核心验证
    # ---------------------------------------------------------------

    assert station_count >= 2, (
        f"广州 3 号线最终站点数量异常: {station_count}"
    )

    assert relation_id is not None, (
        "没有选择任何 OSM Relation"
    )

    # 当前 OSM 数据下，广州 3 号线应当属于 ref=3。
    #
    # 不把 Relation ID 写死为某一个 ID，因为 OSM Relation 未来可能变化。
    # 这里读取实际 Relation 并检查 ref。
    relation_result = rb._call_relation_tracks(
        city,
        line_name,
        bbox,
    )

    candidates = list(
        relation_result.get("candidates", []) or []
    )

    assert candidates, "Overpass 没有返回广州 3 号线候选 Relation"

    selected = None

    for candidate in candidates:
        relation = candidate.get("relation", {}) or {}

        if relation.get("id") == relation_id:
            selected = candidate
            break

    assert selected is not None, (
        f"最终 Relation {relation_id} 不在本次 Overpass 候选集中"
    )

    tags = selected.get("relation", {}).get("tags", {}) or {}

    ref = str(
        tags.get("ref")
        or selected.get("relation", {}).get("ref")
        or ""
    ).strip()

    name = str(
        tags.get("name")
        or selected.get("relation", {}).get("name")
        or ""
    ).strip()

    print("\n")
    print("=" * 80)
    print("最终 Relation 身份检查")
    print("=" * 80)
    print(f"Relation ID : {relation_id}")
    print(f"ref         : {ref}")
    print(f"name        : {name}")
    print("=" * 80)

    # 必须是 3，而不能是 13 / 23 / 33 等。
    assert ref == "3", (
        f"严重错误：广州 3 号线最终选择了错误 Relation: "
        f"ref={ref}, name={name}, id={relation_id}"
    )

    # 名称也不能包含“13号线”。
    assert not re.search(
        r"13\s*号\s*线",
        unicodedata.normalize("NFKC", name),
    ), (
        f"严重错误：3 号线误选 13 号线 Relation: {name}"
    )

    print("\n✅ 广州 3 号线 Relation 身份正确")
    print("✅ 3号线未误匹配13号线")
    print(f"✅ 最终 Relation = {relation_id}")
    print(f"✅ ref = {ref}")
    print(f"✅ 最终站点 = {station_count}")
    print("=" * 80)


# ---------------------------------------------------------------------------
# 3. 独立执行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main(
        [
            "-q",
            "-s",
            str(Path(__file__).resolve()),
        ]
    )
