from metrogis.api.overpass import normalize_relation_name
from metrogis.parser import route_builder as rb


def _candidate(relation_id, identity_score, names, start_node):
    node_ids = [start_node + i for i in range(len(names))]
    stops = [
        {"ref": node_id, "role": "stop", "index": index}
        for index, node_id in enumerate(node_ids)
    ]
    stop_nodes = {
        node_id: {
            "id": node_id,
            "lat": 31.0 + index * 0.01,
            "lng": 121.0 + index * 0.01,
            "name": name,
        }
        for index, (node_id, name) in enumerate(zip(node_ids, names))
    }
    return {
        "relation": {
            "id": relation_id,
            "tags": {
                "name": f"11号线：{names[0]} -> {names[-1]}",
            },
            "_score": identity_score,
        },
        "stops": stops,
        "stop_nodes": stop_nodes,
    }


def test_relation_name_normalization_supports_full_width_colon():
    assert normalize_relation_name("11号线：迪士尼 -> 嘉定北") == "11号线"
    assert normalize_relation_name("11号线:迪士尼 -> 嘉定北") == "11号线"


def test_identity_score_beats_station_count_without_official_yaml(monkeypatch):
    monkeypatch.setattr(
        rb,
        "_call_relation_tracks",
        lambda *args, **kwargs: {
            "candidates": [
                _candidate(
                    5611110,
                    140,
                    ["迪士尼", "花桥", "浦东"],
                    1000,
                ),
                _candidate(
                    16025193,
                    120,
                    ["苏州1", "苏州2", "苏州3", "苏州4", "苏州5", "苏州6", "苏州7"],
                    2000,
                ),
            ]
        },
    )

    result = rb._discover_stations_from_relation(
        "上海",
        "11号线",
        (),
        [],
    )

    assert result is not None
    assert result["relation_id"] == 5611110
    assert result["identity_score"] == 140
    assert result["coverage"] == 0.0
    assert result["inserted_count"] == 3


def test_official_station_coverage_still_beats_identity_score(monkeypatch):
    monkeypatch.setattr(
        rb,
        "_call_relation_tracks",
        lambda *args, **kwargs: {
            "candidates": [
                _candidate(100, 70, ["A", "B", "C"], 3000),
                _candidate(200, 140, ["X", "Y", "Z"], 4000),
            ]
        },
    )

    result = rb._discover_stations_from_relation(
        "测试市",
        "1号线",
        (),
        [
            {"name": "A"},
            {"name": "B"},
            {"name": "C"},
        ],
    )

    assert result is not None
    assert result["relation_id"] == 100
    assert result["coverage"] == 1.0
    assert result["identity_score"] == 70
