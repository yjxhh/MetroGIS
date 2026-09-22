"""
MetroGIS Parser Route Builder V6.7-2.1

全国化站点构建器（V6.7-2.1）

核心设计：
1. OSM Relation 的 stop sequence 是线路站点发现的第一数据源。
2. china_metro.yaml 只承担官方名称、别名和人工元数据作用，不再决定站点数量。
3. 当 Relation 比 YAML 多站时，自动把 Relation 中新增站点插入最终线路。
4. 当 Relation 与 YAML 方向相反时，自动翻转 Relation stop sequence。
5. 只有 Relation 数据不足或不可用时，才回退到现有 get_line_stations()。
6. 不修改 YAML，不为单个城市/线路写特殊规则。
7. 保持 create_route(city, line, bbox) / build_route 等旧调用兼容。
8. V6.7-2：同一线路多个 OSM Relation 先形成 Route Master，再区分 Main / Branch / Partial / Variant。
9. V6.7-2.1：统一 Route Master overlap 指标为 0~1，增加 shared_stops / coverage / endpoint_match / confidence 质量指标。

与 geometry/route_builder.py V10.1 的职责分离：
- 本文件：决定 Line.stations 的最终站点集合与顺序。
- geometry/route_builder.py：根据 Relation Way 链重建线路几何。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import importlib
import inspect
import math
import re
import unicodedata

from metrogis.api.overpass import get_line_relation_tracks
from metrogis.api.station import get_line_stations
from metrogis.parser.station_matcher import station_name_score
from metrogis.resources.loader import get_station_list


# ---------------------------------------------------------------------------
# Fallback models
# ---------------------------------------------------------------------------


@dataclass
class _FallbackStation:
    name: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    order: int = 0


@dataclass
class _FallbackLine:
    name: str
    city: str = ""
    stations: List[Any] = None
    geometry: List[list] = None

    def __post_init__(self) -> None:
        if self.stations is None:
            self.stations = []
        if self.geometry is None:
            self.geometry = []


# ---------------------------------------------------------------------------
# Generic object helpers
# ---------------------------------------------------------------------------


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    """从 dict 或对象读取属性。"""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _point(value: Any) -> Optional[Tuple[float, float]]:
    """统一成 (lng, lat)。"""
    if value is None:
        return None

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        lon = _safe_float(value[0])
        lat = _safe_float(value[1])
        if lon is not None and lat is not None:
            return lon, lat

    lon = _safe_float(_get(value, "lng", "lon", "longitude"))
    lat = _safe_float(_get(value, "lat", "latitude"))
    if lon is None or lat is None:
        return None
    return lon, lat


def _station_name(value: Any) -> str:
    """统一读取站点名称。

    重要：resources.loader.get_station_list() 的 stations 项在当前 YAML
    中是纯字符串（例如 ``"南站"``），而 OSM node 通常是 dict 并把名称
    放在 ``tags.name``。两种输入必须统一处理。
    """
    if isinstance(value, str):
        return _clean_text(value)

    if isinstance(value, bytes):
        try:
            return _clean_text(value.decode("utf-8"))
        except UnicodeDecodeError:
            return _clean_text(value.decode(errors="ignore"))

    name = _clean_text(
        _get(
            value,
            "name",
            "station_name",
            "title",
            "display_name",
            default="",
        )
    )
    if name:
        return name

    # OSM 元素通常把名称放在 tags.name，而不是顶层 name。
    tags = _get(value, "tags", default=None)
    if isinstance(tags, dict):
        for key in ("name", "name:zh", "name:en", "official_name"):
            candidate = _clean_text(tags.get(key))
            if candidate:
                return candidate

    return ""


def _station_point(value: Any) -> Optional[Tuple[float, float]]:
    point = _get(
        value,
        "point",
        "geometry",
        "coordinate",
        "coordinates",
        default=None,
    )
    if point is not None:
        parsed = _point(point)
        if parsed is not None:
            return parsed

    return _point(value)


def _station_id(value: Any) -> Optional[Any]:
    """从各种 OSM Relation stop / node 结构中提取标准化节点 ID。"""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # 直接的数字字符串。
        try:
            return int(text)
        except ValueError:
            pass
        # 兼容 node/123、n123、node:123 等键形式。
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else text

    if isinstance(value, dict):
        # 标准 OSM element/member。
        for key in ("id", "ref", "node_id", "node"):
            if key not in value:
                continue
            nested = value[key]
            if isinstance(nested, dict):
                nested_id = _station_id(nested)
                if nested_id is not None:
                    return nested_id
            else:
                nested_id = _station_id(nested)
                if nested_id is not None:
                    return nested_id

        # 某些封装把原始元素放到 member/element/raw 下。
        for key in ("member", "element", "raw"):
            nested = value.get(key)
            nested_id = _station_id(nested)
            if nested_id is not None:
                return nested_id
        return None

    for attr in ("id", "ref", "node_id", "node", "member", "element"):
        try:
            nested = getattr(value, attr)
        except Exception:
            continue
        nested_id = _station_id(nested)
        if nested_id is not None:
            return nested_id

    return None


def _build_stop_node_index(stop_nodes: Any) -> Dict[int, Any]:
    """把 stop_nodes 的各种键形式统一成 int(node_id) -> node。"""
    index: Dict[int, Any] = {}
    if not stop_nodes:
        return index

    items = stop_nodes.items() if isinstance(stop_nodes, dict) else enumerate(stop_nodes)
    try:
        iterator = list(items)
    except Exception:
        return index

    for key, node in iterator:
        candidates = (key, node)
        for candidate in candidates:
            sid = _station_id(candidate)
            if sid is None:
                continue
            try:
                index[int(sid)] = node
            except (TypeError, ValueError):
                continue

    return index


def _lookup_stop_node(
    stop: Any,
    stop_nodes: Any,
    stop_node_index: Optional[Dict[int, Any]] = None,
) -> Any:
    """兼容 int/string/node/... 多种 stop_nodes 键形式。"""
    sid = _station_id(stop)
    if sid is None:
        return None

    index = stop_node_index if stop_node_index is not None else _build_stop_node_index(stop_nodes)
    try:
        node = index.get(int(sid))
    except (TypeError, ValueError):
        node = None
    if node is not None:
        return node

    if isinstance(stop_nodes, dict):
        for key in (sid, str(sid), f"node/{sid}", f"n{sid}"):
            if key in stop_nodes:
                return stop_nodes[key]

    return None


def _relation_stop_record(
    stop: Any,
    stop_nodes: Optional[Dict[Any, Any]],
    stop_node_index: Optional[Dict[int, Any]] = None,
) -> Dict[str, Any]:
    """把 Relation stop 统一成内部记录。"""
    sid = _station_id(stop)
    node = _lookup_stop_node(stop, stop_nodes, stop_node_index)

    name = _station_name(stop)
    if not name and isinstance(stop, dict):
        for key in ("node", "member", "element", "raw"):
            nested = stop.get(key)
            name = _station_name(nested)
            if name:
                break
    if not name and node is not None:
        name = _station_name(node)

    point = _station_point(stop)
    if point is None and isinstance(stop, dict):
        for key in ("node", "member", "element", "raw"):
            nested_point = _station_point(stop.get(key))
            if nested_point is not None:
                point = nested_point
                break
    if point is None and node is not None:
        point = _station_point(node)

    return {
        "id": sid,
        "name": name,
        "point": point,
        "raw": stop,
        "node": node,
    }


def _normalize_station_name(value: Any) -> str:
    """线路站点基础名称归一化。

    这里不依赖 station_matcher.py，作为全国化解析的最低可靠匹配层：
    - Unicode NFKC 统一全角/兼容字符
    - 去除空白、常见分隔符
    - 保留中文名称
    - “XXX站”与“XXX”视为同一站名
    """
    text = _clean_text(value)
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\s\u3000]+", "", text)
    text = re.sub(r"[\(\)\[\]{}<>，。、“”‘’：:；;、/\\|·•_-]+", "", text)

    if text.endswith("站") and len(text) > 1:
        text = text[:-1]
    return text


def _basic_station_name_score(a: Any, b: Any) -> float:
    """本地基础站名评分，避免外部 station_matcher 版本差异导致全 0。"""
    na = _normalize_station_name(a)
    nb = _normalize_station_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0

    # 只接受短距离的保守包含关系，避免“天津站/天津宾馆”之类误配。
    if min(len(na), len(nb)) >= 3:
        if na in nb or nb in na:
            if abs(len(na) - len(nb)) <= 2:
                return 80.0
    return 0.0


def _station_match_score(a: Any, b: Any) -> float:
    """优先使用项目 matcher，失败时回退到本文件基础评分。"""
    try:
        score = float(station_name_score(a, b))
    except Exception:
        score = 0.0
    if score > 0:
        return score
    return _basic_station_name_score(a, b)


def _distance_m(a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]) -> float:
    """不引入新的地理依赖，用局部等距近似做小范围站点比较。"""
    if a is None or b is None:
        return float("inf")
    lon1, lat1 = a
    lon2, lat2 = b
    lat0 = math.radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * 111320.0 * max(0.01, math.cos(lat0))
    dy = (lat2 - lat1) * 110540.0
    return math.hypot(dx, dy)


# ---------------------------------------------------------------------------
# Line / station object construction
# ---------------------------------------------------------------------------


def _find_class(class_name: str, modules: Sequence[str]) -> Optional[type]:
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
        except (ImportError, ModuleNotFoundError):
            continue
        cls = getattr(module, class_name, None)
        if isinstance(cls, type):
            return cls
    return None


def _make_station(name: str, point: Optional[Tuple[float, float]], order: int) -> Any:
    lat = point[1] if point else None
    lng = point[0] if point else None

    station_cls = _find_class(
        "Station",
        (
            "metrogis.models",
            "metrogis.models.subway",
            "metrogis.models.route",
            "metrogis.models.line",
            "metrogis.models.network",
            "metrogis.parser.models",
        ),
    )

    if station_cls is None:
        return _FallbackStation(name=name, lat=lat, lng=lng, order=order)

    attempts = (
        {"name": name, "lat": lat, "lng": lng, "order": order},
        {"name": name, "latitude": lat, "longitude": lng, "order": order},
        {"name": name, "lat": lat, "lng": lng},
        {"name": name},
    )

    for kwargs in attempts:
        try:
            station = station_cls(**kwargs)
            for attr, value in (
                ("name", name),
                ("lat", lat),
                ("lng", lng),
                ("order", order),
            ):
                try:
                    setattr(station, attr, value)
                except Exception:
                    pass
            return station
        except TypeError:
            continue

    try:
        station = station_cls(name, lat, lng, order)
        return station
    except Exception:
        return _FallbackStation(name=name, lat=lat, lng=lng, order=order)


def _make_line(city_name: str, line_name: str) -> Any:
    full_name = f"{city_name}{line_name}"
    line_cls = _find_class(
        "Line",
        (
            "metrogis.models",
            "metrogis.models.network",
            "metrogis.models.route",
            "metrogis.models.subway",
            "metrogis.models.station",
            "metrogis.parser.models",
        ),
    )

    # 老版本项目没有 Line，而是 SubwayLine。
    if line_cls is None:
        line_cls = _find_class(
            "SubwayLine",
            (
                "metrogis.models",
                "metrogis.models.subway",
                "metrogis.models.route",
            ),
        )

    if line_cls is None:
        line = _FallbackLine(name=full_name, city=city_name)
    else:
        line = None
        attempts = (
            {"name": full_name, "city": city_name},
            {"name": full_name},
            {"line_name": line_name, "city_name": city_name},
            {"line_name": line_name},
        )
        for kwargs in attempts:
            try:
                line = line_cls(**kwargs)
                break
            except TypeError:
                continue
        if line is None:
            try:
                line = line_cls(full_name)
            except Exception:
                line = _FallbackLine(name=full_name, city=city_name)

    # 保持现有项目一直使用的 ID / name 习惯。
    for attr, value in (
        ("name", full_name),
        ("line_name", line_name),
        ("city", city_name),
        ("city_name", city_name),
        ("id", f"{city_name}_{line_name}"),
        ("line_id", f"{city_name}_{line_name}"),
    ):
        try:
            setattr(line, attr, value)
        except Exception:
            pass

    if not hasattr(line, "stations") or getattr(line, "stations", None) is None:
        try:
            line.stations = []
        except Exception:
            pass

    if not hasattr(line, "geometry") or getattr(line, "geometry", None) is None:
        try:
            line.geometry = []
        except Exception:
            pass

    return line


# ---------------------------------------------------------------------------
# YAML / Relation sequence handling
# ---------------------------------------------------------------------------


def _official_stations(city_name: str, line_name: str) -> List[Any]:
    try:
        value = get_station_list(city_name, line_name)
    except TypeError:
        value = get_station_list(city=city_name, line=line_name)
    except Exception as exc:
        print(f"读取官方站点列表失败: {exc}")
        return []

    return list(value or [])


def _official_records(stations: Sequence[Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for station in stations:
        name = _station_name(station)
        if not name:
            continue
        records.append(
            {
                "name": name,
                "point": _station_point(station),
                "raw": station,
            }
        )
    return records


def _sequence_alignment(
    official: Sequence[Dict[str, Any]],
    relation: Sequence[Dict[str, Any]],
) -> Tuple[List[Optional[int]], int, float]:
    """
    全局子序列 DP。

    输出：
      relation_index -> official_index / None

    允许：
      - OSM 多出站点：自动插入
      - YAML 多出站点：不强行塞进 Relation
      - 名称轻微不同：使用 station_name_score
    """
    n = len(official)
    m = len(relation)
    if n == 0 or m == 0:
        return [None] * m, 0, 0.0

    # dp[i][j] = (match_count, score)
    dp: List[List[Tuple[int, float]]] = [
        [(0, 0.0) for _ in range(m + 1)]
        for _ in range(n + 1)
    ]

    choice: List[List[str]] = [
        ["" for _ in range(m + 1)]
        for _ in range(n + 1)
    ]

    def better(
        a: Tuple[int, float],
        b: Tuple[int, float],
    ) -> Tuple[int, float]:
        if a[0] != b[0]:
            return a if a[0] > b[0] else b
        return a if a[1] >= b[1] else b

    for i in range(1, n + 1):
        dp[i][0] = (0, 0.0)
        choice[i][0] = "skip_official"

    for j in range(1, m + 1):
        dp[0][j] = (0, 0.0)
        choice[0][j] = "skip_relation"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = dp[i - 1][j]
            best_choice = "skip_official"

            candidate = dp[i][j - 1]
            if better(candidate, best) == candidate and candidate != best:
                best = candidate
                best_choice = "skip_relation"

            score = _station_match_score(
                official[i - 1]["name"],
                relation[j - 1]["name"],
            )
            if score > 0:
                candidate = (
                    dp[i - 1][j - 1][0] + 1,
                    dp[i - 1][j - 1][1] + score,
                )
                if better(candidate, best) == candidate:
                    best = candidate
                    best_choice = "match"

            dp[i][j] = best
            choice[i][j] = best_choice

    mapping: List[Optional[int]] = [None] * m
    i, j = n, m
    while i > 0 or j > 0:
        c = choice[i][j] if i >= 0 and j >= 0 else ""
        if i > 0 and j > 0 and c == "match":
            mapping[j - 1] = i - 1
            i -= 1
            j -= 1
        elif j > 0 and c == "skip_relation":
            j -= 1
        elif i > 0:
            i -= 1
        else:
            break

    return mapping, dp[n][m][0], dp[n][m][1]


def _orient_relation(
    official: Sequence[Dict[str, Any]],
    relation: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], bool, int, float]:
    direct = list(relation)
    reverse = list(reversed(relation))

    direct_map, direct_count, direct_score = _sequence_alignment(official, direct)
    reverse_map, reverse_count, reverse_score = _sequence_alignment(official, reverse)

    # 数量优先、名称总分其次；完全相同得分时保留 Relation 原方向。
    if (reverse_count, reverse_score) > (direct_count, direct_score):
        return reverse, True, reverse_count, reverse_score
    return direct, False, direct_count, direct_score


def _merge_relation_with_official(
    official: Sequence[Dict[str, Any]],
    oriented_relation: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, float, int]:
    """
    以 Relation 为主序列，将能匹配到的 YAML 官方名字覆盖到对应 OSM stop；
    Relation 中无法匹配的 stop 自动保留。

    返回：
      merged, matched_count, score, inserted_relation_count
    """
    mapping, matched_count, matched_score = _sequence_alignment(
        official,
        oriented_relation,
    )

    merged: List[Dict[str, Any]] = []
    used_official: set[int] = set()
    inserted_relation_count = 0

    for relation_index, relation_record in enumerate(oriented_relation):
        official_index = mapping[relation_index]
        if official_index is not None:
            official_record = official[official_index]
            used_official.add(official_index)
            name = official_record["name"] or relation_record["name"]
            point = relation_record["point"] or official_record["point"]
            merged.append(
                {
                    "name": name,
                    "point": point,
                    "source": "relation+official",
                    "relation_id": relation_record.get("id"),
                    "official_index": official_index,
                    "raw": relation_record.get("raw"),
                }
            )
        else:
            # Relation 有、YAML 没有：这是全国化最关键的自动补站路径。
            if relation_record.get("name") or relation_record.get("point"):
                merged.append(
                    {
                        "name": relation_record.get("name", ""),
                        "point": relation_record.get("point"),
                        "source": "relation",
                        "relation_id": relation_record.get("id"),
                        "official_index": None,
                        "raw": relation_record.get("raw"),
                    }
                )
                inserted_relation_count += 1

    # 未匹配官方站点如果数量很少，尝试按照相邻官方站点位置插回去。
    # 只在有可靠坐标、且 Relation 中没有明显对应点时执行，避免破坏真实 OSM 顺序。
    unmatched_official = [
        official[i]
        for i in range(len(official))
        if i not in used_official
    ]

    if unmatched_official and merged:
        for missing in unmatched_official:
            if missing.get("point") is None:
                continue

            # 找最近 Relation station 的索引，只用于判断是否属于当前线路；
            # 不会凭空把远距离的官方站点加入路线。
            distances = [
                _distance_m(missing["point"], item.get("point"))
                for item in merged
            ]
            if not distances:
                continue

            minimum = min(distances)
            # 500m 是保守阈值，只允许处理轻微 OSM/YAML 拆分差异。
            if minimum > 500.0:
                continue

            nearest_index = distances.index(minimum)
            insert_index = nearest_index + (1 if nearest_index < len(merged) else 0)
            merged.insert(
                insert_index,
                {
                    "name": missing["name"],
                    "point": missing["point"],
                    "source": "official-near-relation",
                    "relation_id": None,
                    "official_index": None,
                    "raw": missing.get("raw"),
                },
            )

    return merged, matched_count, matched_score, inserted_relation_count


# ---------------------------------------------------------------------------
# Relation API compatibility
# ---------------------------------------------------------------------------


def _call_relation_tracks(
    city_name: str,
    line_name: str,
    bbox: Sequence[float],
) -> Dict[str, Any]:
    """
    调用当前 Overpass Relation API。

    不假定 get_line_relation_tracks() 的参数顺序；优先依据真实函数签名
    传 keyword arguments，避免不同版本之间出现“expected 4, got 3”之类的
    参数错位。只有签名无法使用时才尝试兼容旧版本的位置参数。
    """
    func = get_line_relation_tracks

    # 1. 优先按真实签名构造 kwargs。
    try:
        params = inspect.signature(func).parameters
        aliases = {
            "city": city_name,
            "city_name": city_name,
            "cityname": city_name,
            "line": line_name,
            "line_name": line_name,
            "name": line_name,
            "bbox": bbox,
            "line_ref": None,
            "route_ref": None,
            "ref": None,
        }

        kwargs: Dict[str, Any] = {}
        for parameter_name, parameter in params.items():
            if parameter_name in aliases:
                value = aliases[parameter_name]
                # 不主动给有默认值的 ref 传 None，减少版本差异。
                if value is not None:
                    kwargs[parameter_name] = value

        required_missing = [
            name
            for name, parameter in params.items()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            and name not in kwargs
        ]

        if not required_missing:
            result = func(**kwargs)
            if isinstance(result, dict):
                return result
            return {}
    except Exception as exc:
        # 只有调用/签名本身失败才进入兼容路径；网络错误也统一兜底。
        print(f"Relation 查询尝试失败: {exc}")

    # 2. 兼容历史版本的常见签名。
    attempts = (
        ((city_name, line_name, bbox, None), {}),
        ((city_name, line_name, bbox), {}),
        ((line_name, bbox, None, city_name), {}),
        ((line_name, bbox, None), {}),
        ((line_name, bbox), {}),
    )

    for args, kwargs in attempts:
        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict):
                return result
            return {}
        except (TypeError, ValueError) as exc:
            print(f"Relation 参数兼容尝试失败: {exc}")
            continue
        except Exception as exc:
            print(f"Relation 查询失败: {exc}")
            return {}

    return {}


def _candidate_records(candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    stops = list(candidate.get("stops", []) or [])
    stop_nodes = candidate.get("stop_nodes", {}) or {}
    stop_node_index = _build_stop_node_index(stop_nodes)

    records = [
        _relation_stop_record(stop, stop_nodes, stop_node_index)
        for stop in stops
    ]

    # 诊断信息：正常 Relation 至少应该能解析出站名。
    named = sum(1 for record in records if record.get("name"))
    if records and named == 0:
        print(
            f"Relation Stop 名称解析失败: {len(records)} 个 stop 均未获得名称；"
            f"stop_nodes={len(stop_node_index)}"
        )
    elif records:
        sample = ", ".join(
            f"{idx}:{record.get('name') or '-'}"
            for idx, record in enumerate(records[:5])
        )
        print(f"Relation Stop 名称样例: {sample}")

    return records


def _relation_candidate_label(candidate: Dict[str, Any]) -> str:
    relation = candidate.get("relation", {}) or {}
    tags = relation.get("tags", {}) or {}
    return _clean_text(tags.get("name") or relation.get("name") or relation.get("id"))


def _line_identity_key(value: Any) -> str:
    """提取可用于全国化精确线路身份比较的线路代码。

    重点避免字符串包含误判，例如：
      3号线 不能命中 13号线
      11号线 不能命中 111号线

    优先从 ``X号线`` / ``X线`` 中提取 X；对于 F3、APM 等纯线路代码
    直接保留字母数字组合。无法抽取代码时，返回归一化后的完整文本。
    """
    text = _clean_text(value)
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[\s\u3000]+", "", text)

    # 中文/拉丁混合的“3号线”“F3号线”“APM线”等。
    match = re.search(
        r"([a-z]*\d+[a-z]*)号线",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).lower()

    match = re.search(
        r"([a-z]+\d+[a-z]*|\d+[a-z]*|[a-z]{2,8})线",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).lower()

    # 处理“地铁广佛线”一类没有数字的名称。
    text_without_prefix = re.sub(
        r"^(?:地铁|轨道交通|城市轨道交通|metro)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    nonnumeric_match = re.search(
        r"([a-z0-9\u3400-\u9fff]+线)(?=[:：→>]|$)",
        text_without_prefix,
        flags=re.IGNORECASE,
    )
    if nonnumeric_match:
        return nonnumeric_match.group(1).lower()

    if text_without_prefix.endswith("线") and len(text_without_prefix) > 1:
        return text_without_prefix.lower()

    # APM / LRT / F3 等裸线路代码。
    compact = re.sub(r"[^a-z0-9]+", "", text)
    if re.fullmatch(r"[a-z]*\d+[a-z]*|[a-z]{2,8}", compact):
        return compact.lower()

    # 非数字线路（如“广佛线”）没有可靠的通用代码，只能做完整文本比较。
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", text)


def _relation_identity_matches(
    line_name: str,
    candidate: Dict[str, Any],
) -> bool:
    """判断 Relation 是否与目标线路拥有精确的线路身份。

    ``ref`` 是第一依据；没有 ref 时才退回 Relation name。这里故意不使用
    ``target in candidate`` 之类包含匹配，因为它会把“3号线”错误匹配到
    “13号线”。
    """
    target_key = _line_identity_key(line_name)
    if not target_key:
        return False

    relation = candidate.get("relation", {}) or {}
    tags = relation.get("tags", {}) or {}

    ref_value = tags.get("ref") or relation.get("ref")
    ref_key = _line_identity_key(ref_value)
    if ref_key:
        return ref_key == target_key

    name_value = tags.get("name") or relation.get("name")
    name_key = _line_identity_key(name_value)
    return bool(name_key) and name_key == target_key



# ---------------------------------------------------------------------------
# V6.7-2 Route Master / Main / Branch / Partial resolution
# ---------------------------------------------------------------------------


_ROUTE_MASTER_IDENTITY_TOLERANCE = 15.0
_ROUTE_MASTER_SEQUENCE_OVERLAP = 0.60
_ROUTE_MASTER_DIRECTION_OVERLAP = 0.85
_ROUTE_MASTER_PARTIAL_OVERLAP = 0.80
_ROUTE_MASTER_BRANCH_MIN_COMMON = 3


def _relation_record_names(records: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        _normalize_station_name(record.get("name", ""))
        for record in records
        if _normalize_station_name(record.get("name", ""))
    ]


def _ordered_common_station_count(
    a: Sequence[Dict[str, Any]],
    b: Sequence[Dict[str, Any]],
) -> int:
    """Count the longest ordered common subsequence by normalized station name."""
    a_names = _relation_record_names(a)
    b_names = _relation_record_names(b)
    if not a_names or not b_names:
        return 0

    n = len(a_names)
    m = len(b_names)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        ai = a_names[i - 1]
        for j in range(1, m + 1):
            if ai == b_names[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]


def _station_name_set(records: Sequence[Dict[str, Any]]) -> set[str]:
    return {
        normalized
        for normalized in (_normalize_station_name(r.get("name", "")) for r in records)
        if normalized
    }


def _sequence_overlap_metrics(
    a: Sequence[Dict[str, Any]],
    b: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return normalized ordered-overlap metrics.

    All ratio fields are guaranteed to stay in [0, 1]. ``shared_stops`` is
    the longest ordered common subsequence length.
    """
    a_count = len(_relation_record_names(a))
    b_count = len(_relation_record_names(b))
    if not a_count or not b_count:
        return {
            "shared_stops": 0,
            "a_stops": a_count,
            "b_stops": b_count,
            "overlap_ratio": 0.0,
            "a_coverage": 0.0,
            "b_coverage": 0.0,
            "shorter_coverage": 0.0,
        }

    common = _ordered_common_station_count(a, b)
    common = max(0, min(common, a_count, b_count))
    overlap_ratio = common / min(a_count, b_count)
    a_coverage = common / a_count
    b_coverage = common / b_count
    shorter_coverage = max(a_coverage, b_coverage)

    return {
        "shared_stops": common,
        "a_stops": a_count,
        "b_stops": b_count,
        "overlap_ratio": min(1.0, max(0.0, overlap_ratio)),
        "a_coverage": min(1.0, max(0.0, a_coverage)),
        "b_coverage": min(1.0, max(0.0, b_coverage)),
        "shorter_coverage": min(1.0, max(0.0, shorter_coverage)),
    }


def _sequence_overlap(a: Sequence[Dict[str, Any]], b: Sequence[Dict[str, Any]]) -> float:
    """Ordered overlap relative to the shorter Relation, normalized to [0, 1]."""
    return float(_sequence_overlap_metrics(a, b)["overlap_ratio"])


def _reverse_sequence_overlap(a: Sequence[Dict[str, Any]], b: Sequence[Dict[str, Any]]) -> float:
    return _sequence_overlap(a, list(reversed(b)))


def _relation_endpoint_names(records: Sequence[Dict[str, Any]]) -> Tuple[str, str]:
    names = [
        _normalize_station_name(record.get("name", ""))
        for record in records
        if _normalize_station_name(record.get("name", ""))
    ]
    if not names:
        return "", ""
    return names[0], names[-1]


def _candidate_identity_score(candidate: Dict[str, Any]) -> float:
    relation = candidate.get("relation", {}) or {}
    try:
        return float(relation.get("_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _candidate_metadata(candidate: Dict[str, Any]) -> Dict[str, Any]:
    relation = candidate.get("relation", {}) or {}
    tags = relation.get("tags", {}) or {}
    return {
        "id": relation.get("id"),
        "name": _clean_text(tags.get("name") or relation.get("name") or ""),
        "ref": _clean_text(tags.get("ref") or relation.get("ref") or ""),
        "type": _clean_text(tags.get("type") or relation.get("type") or ""),
        "route": _clean_text(tags.get("route") or relation.get("route") or ""),
        "network": _clean_text(tags.get("network") or relation.get("network") or ""),
        "operator": _clean_text(tags.get("operator") or relation.get("operator") or ""),
        "route_master": _clean_text(
            tags.get("route_master")
            or relation.get("route_master")
            or candidate.get("route_master")
            or ""
        ),
        "route_master_id": relation.get("route_master_id") or candidate.get("route_master_id"),
    }


def _identity_cohort(evaluated: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep candidates close to the best identity tier.

    Same-number routes from another nearby network/city sometimes survive the
    exact ref check. V6.7-2 treats the Overpass identity score as a cohort
    signal: candidates well below the best identity tier do not participate
    in Main/Branch inference. This is intentionally relative, not a hard
    national threshold.
    """
    if not evaluated:
        return []

    max_score = max(item["identity_score"] for item in evaluated)
    cohort = [
        item
        for item in evaluated
        if item["identity_score"] >= max_score - _ROUTE_MASTER_IDENTITY_TOLERANCE
    ]

    # Never return an empty cohort because of NaN/odd API values.
    return cohort or list(evaluated)


def _pair_route_directions(
    evaluated: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Pair opposite-direction route relations using normalized quality metrics."""
    pairs: List[Dict[str, Any]] = []
    used: set[int] = set()

    for i, left in enumerate(evaluated):
        left_id = left.get("relation_id")
        if left_id in used:
            continue

        best_pair = None
        for j in range(i + 1, len(evaluated)):
            right = evaluated[j]
            right_id = right.get("relation_id")
            if right_id in used or left_id == right_id:
                continue

            metrics = _sequence_overlap_metrics(left["records"], list(reversed(right["records"])))
            raw_overlap = metrics["overlap_ratio"]
            if raw_overlap < _ROUTE_MASTER_DIRECTION_OVERLAP:
                continue

            left_start, left_end = _relation_endpoint_names(left["records"])
            right_start, right_end = _relation_endpoint_names(right["records"])
            endpoint_match = bool(
                left_start
                and left_end
                and right_start
                and right_end
                and left_start == right_end
                and left_end == right_start
            )

            # Confidence is deliberately normalized to [0, 1]. Endpoint match
            # is a quality signal, not an additive bonus that can make overlap > 1.
            confidence = (0.80 * raw_overlap) + (0.20 if endpoint_match else 0.0)
            confidence = min(1.0, max(0.0, confidence))

            length_delta = abs(left["station_count"] - right["station_count"])
            candidate_key = (
                confidence,
                raw_overlap,
                1 if endpoint_match else 0,
                -length_delta,
                right["station_count"],
            )
            if best_pair is None or candidate_key > best_pair[0]:
                best_pair = (candidate_key, j, metrics, endpoint_match, confidence)

        if best_pair is not None:
            _, j, metrics, endpoint_match, confidence = best_pair
            right = evaluated[j]
            pairs.append(
                {
                    "forward_id": left_id,
                    "reverse_id": right.get("relation_id"),
                    "shared_stops": metrics["shared_stops"],
                    "overlap_ratio": metrics["overlap_ratio"],
                    "forward_coverage": metrics["a_coverage"],
                    "reverse_coverage": metrics["b_coverage"],
                    "endpoint_match": endpoint_match,
                    "confidence": confidence,
                    # Backward-compatible field; guaranteed <= 1.
                    "overlap": metrics["overlap_ratio"],
                }
            )
            used.add(left_id)
            used.add(right.get("relation_id"))

    return pairs


def _classify_against_main(
    item: Dict[str, Any],
    main: Dict[str, Any],
    paired_main_ids: set[int],
) -> Tuple[str, Dict[str, Any]]:
    item_id = item.get("relation_id")
    main_id = main.get("relation_id")
    if item_id == main_id:
        return "main", {
            "shared_stops": item["station_count"],
            "item_coverage": 1.0,
            "main_coverage": 1.0,
            "overlap_ratio": 1.0,
            "reverse_overlap_ratio": 1.0,
            "exclusive_stops": 0,
            "orientation": "same",
        }
    if item_id in paired_main_ids:
        return "main", {
            "shared_stops": item["station_count"],
            "item_coverage": 1.0,
            "main_coverage": 1.0,
            "overlap_ratio": 1.0,
            "reverse_overlap_ratio": 1.0,
            "exclusive_stops": 0,
            "orientation": "reverse",
        }

    item_names = _station_name_set(item["records"])
    main_names = _station_name_set(main["records"])
    common_set = item_names & main_names
    exclusive = len(item_names - main_names)

    direct_metrics = _sequence_overlap_metrics(item["records"], main["records"])
    reverse_metrics = _sequence_overlap_metrics(item["records"], list(reversed(main["records"])))
    overlap = direct_metrics["overlap_ratio"]
    reverse_overlap = reverse_metrics["overlap_ratio"]
    common = len(common_set)

    if reverse_overlap > overlap:
        best_metrics = reverse_metrics
        orientation = "reverse"
    else:
        best_metrics = direct_metrics
        orientation = "same"

    metrics = {
        "shared_stops": best_metrics["shared_stops"],
        "item_coverage": best_metrics["a_coverage"],
        "main_coverage": best_metrics["b_coverage"],
        "overlap_ratio": best_metrics["overlap_ratio"],
        "reverse_overlap_ratio": reverse_overlap,
        "direct_overlap_ratio": overlap,
        "exclusive_stops": exclusive,
        "orientation": orientation,
    }

    if common >= _ROUTE_MASTER_BRANCH_MIN_COMMON and exclusive >= 2 and max(overlap, reverse_overlap) >= 0.40:
        return "branch", metrics

    if exclusive <= 1 and max(overlap, reverse_overlap) >= _ROUTE_MASTER_PARTIAL_OVERLAP:
        return "partial", metrics

    if max(overlap, reverse_overlap) >= _ROUTE_MASTER_SEQUENCE_OVERLAP:
        return "variant", metrics

    return "unrelated", metrics


def _select_main_route(evaluated: Sequence[Dict[str, Any]], official: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Select the master Main route candidate.

    Main is the longest high-identity route which also carries the best official
    station coverage when YAML is available. Partial/short-turn relations are
    therefore not allowed to win merely because they are recent or numerous.
    """
    if official:
        return max(
            evaluated,
            key=lambda item: (
                item["coverage"],
                item["matched_count"],
                item["matched_score"],
                item["station_count"],
                item["identity_score"],
            ),
        )

    return max(
        evaluated,
        key=lambda item: (
            item["station_count"],
            item["matched_count"],
            item["matched_score"],
            item["identity_score"],
        ),
    )


def _resolve_route_master(
    evaluated: Sequence[Dict[str, Any]],
    official: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve one logical metro line from multiple OSM route Relations."""
    if not evaluated:
        return None

    cohort = _identity_cohort(evaluated)
    main = _select_main_route(cohort, official)

    direction_pairs = _pair_route_directions(cohort)
    paired_main_ids: set[int] = set()
    main_pair = None
    for pair in direction_pairs:
        ids = {pair["forward_id"], pair["reverse_id"]}
        if main.get("relation_id") in ids:
            paired_main_ids.update(ids)
            main_pair = pair
            break

    classifications: List[Dict[str, Any]] = []
    for item in cohort:
        role, metrics = _classify_against_main(item, main, paired_main_ids)
        classifications.append(
            {
                "relation_id": item["relation_id"],
                "relation_name": item["relation_name"],
                "role": role,
                "station_count": item["station_count"],
                "identity_score": item["identity_score"],
                "metrics": metrics,
            }
        )

    branch_items = [
        item for item in cohort
        if _classify_against_main(item, main, paired_main_ids)[0] == "branch"
    ]
    partial_items = [
        item for item in cohort
        if _classify_against_main(item, main, paired_main_ids)[0] == "partial"
    ]
    variant_items = [
        item for item in cohort
        if _classify_against_main(item, main, paired_main_ids)[0] == "variant"
    ]

    master_type = "inferred_route_master"
    explicit_master_ids: set[Any] = set()
    for item in cohort:
        metadata = item.get("metadata", {}) or {}
        master_id = metadata.get("route_master_id")
        if master_id is not None:
            explicit_master_ids.add(master_id)

    if explicit_master_ids:
        master_type = "osm_route_master"

    main_start, main_end = _relation_endpoint_names(main["records"])
    main_pair_quality = None
    if main_pair is not None:
        main_pair_quality = {
            "shared_stops": main_pair.get("shared_stops", 0),
            "overlap_ratio": min(1.0, max(0.0, float(main_pair.get("overlap_ratio", 0.0)))),
            "forward_coverage": min(1.0, max(0.0, float(main_pair.get("forward_coverage", 0.0)))),
            "reverse_coverage": min(1.0, max(0.0, float(main_pair.get("reverse_coverage", 0.0)))),
            "endpoint_match": bool(main_pair.get("endpoint_match", False)),
            "confidence": min(1.0, max(0.0, float(main_pair.get("confidence", 0.0)))),
        }

    return {
        "type": master_type,
        "identity_key": _line_identity_key(main.get("line_name") or main.get("relation_name") or ""),
        "identity_score": max(item["identity_score"] for item in cohort),
        "main": {
            "relation_id": main["relation_id"],
            "relation_name": main["relation_name"],
            "station_count": main["station_count"],
            "records": main["records"],
            "reversed": main["reverse"],
            "coverage": main["coverage"],
            "matched_count": main["matched_count"],
            "matched_score": main["matched_score"],
            "start_station": main_start,
            "end_station": main_end,
        },
        "main_pair": main_pair,
        "main_pair_quality": main_pair_quality,
        "direction_pairs": direction_pairs,
        "branches": [
            {
                "relation_id": item["relation_id"],
                "relation_name": item["relation_name"],
                "station_count": item["station_count"],
                "records": item["records"],
                "reversed": item["reverse"],
                "metrics": _classify_against_main(item, main, paired_main_ids)[1],
            }
            for item in branch_items
        ],
        "partials": [
            {
                "relation_id": item["relation_id"],
                "relation_name": item["relation_name"],
                "station_count": item["station_count"],
                "records": item["records"],
                "reversed": item["reverse"],
                "metrics": _classify_against_main(item, main, paired_main_ids)[1],
            }
            for item in partial_items
        ],
        "variants": [
            {
                "relation_id": item["relation_id"],
                "relation_name": item["relation_name"],
                "station_count": item["station_count"],
                "records": item["records"],
                "reversed": item["reverse"],
                "metrics": _classify_against_main(item, main, paired_main_ids)[1],
            }
            for item in variant_items
        ],
        "classifications": classifications,
        "cohort_relation_ids": [item["relation_id"] for item in cohort],
        "candidate_relation_ids": [item["relation_id"] for item in evaluated],
        "excluded_relation_ids": [
            item["relation_id"]
            for item in evaluated
            if item["relation_id"] not in {member["relation_id"] for member in cohort}
        ],
        "quality": {
            "cohort_size": len(cohort),
            "candidate_size": len(evaluated),
            "branch_count": len(branch_items),
            "partial_count": len(partial_items),
            "variant_count": len(variant_items),
            "unrelated_count": sum(
                1 for item in classifications if item["role"] == "unrelated"
            ),
            "main_pair_confidence": (
                main_pair_quality["confidence"] if main_pair_quality else None
            ),
        },
        "explicit_route_master_ids": list(explicit_master_ids),
    }

def _discover_stations_from_relation(
    city_name: str,
    line_name: str,
    bbox: Sequence[float],
    official_stations: Sequence[Any],
) -> Optional[Dict[str, Any]]:
    result = _call_relation_tracks(city_name, line_name, bbox)
    candidates = list(result.get("candidates", []) or [])
    if not candidates:
        return None

    official = _official_records(official_stations)
    if official:
        print(
            "官方站点名称样例: "
            + ", ".join(
                f"{idx}:{record['name']}"
                for idx, record in enumerate(official[:5])
            )
        )

    evaluated: List[Dict[str, Any]] = []
    rejected_identity = 0

    for candidate in candidates:
        # V6.7-1.1：先做精确线路身份过滤。
        if not _relation_identity_matches(line_name, candidate):
            rejected_identity += 1
            continue

        records = _candidate_records(candidate)
        if len(records) < 2:
            continue

        oriented, reversed_relation, matched_count, matched_score = _orient_relation(
            official,
            records,
        )

        relation = candidate.get("relation", {}) or {}
        identity_score = _candidate_identity_score(candidate)

        official_count = len(official)
        coverage = matched_count / official_count if official_count else 0.0
        station_count = len(oriented)

        evaluated.append(
            {
                "candidate": candidate,
                "records": oriented,
                "reverse": reversed_relation,
                "matched_count": matched_count,
                "matched_score": matched_score,
                "coverage": coverage,
                "identity_score": identity_score,
                "station_count": station_count,
                "relation_id": relation.get("id"),
                "relation_name": _relation_candidate_label(candidate),
                "line_name": line_name,
                "metadata": _candidate_metadata(candidate),
            }
        )

    if rejected_identity:
        print(f"Relation 精确线路身份过滤: 排除 {rejected_identity} 个不匹配候选")

    if not evaluated:
        return None

    # ------------------------------------------------------------------
    # V6.7-2：Route Master / Main / Branch / Partial
    # ------------------------------------------------------------------
    route_master = _resolve_route_master(evaluated, official)
    if route_master is None:
        return None

    # 主路线来自 Route Master，而不是简单地把“最长 Relation”当最终结果。
    main_id = route_master["main"]["relation_id"]
    best = next(
        item for item in evaluated if item["relation_id"] == main_id
    )

    # 输出候选评分。V6.7-2 额外打印角色，方便全国线路诊断。
    print("Route Master Main/Pair 质量:")
    if route_master.get("main_pair_quality"):
        quality = route_master["main_pair_quality"]
        print(
            f"  shared_stops={quality['shared_stops']} | "
            f"overlap={quality['overlap_ratio']:.1%} | "
            f"forward_coverage={quality['forward_coverage']:.1%} | "
            f"reverse_coverage={quality['reverse_coverage']:.1%} | "
            f"endpoint_match={quality['endpoint_match']} | "
            f"confidence={quality['confidence']:.1%}"
        )
    else:
        print("  main_pair=None")

    print("Relation 候选评分:")
    cohort_ids = set(route_master["cohort_relation_ids"])
    class_map = {
        item["relation_id"]: item["role"]
        for item in route_master["classifications"]
    }

    for item in sorted(
        evaluated,
        key=lambda value: (
            value["relation_id"] in cohort_ids,
            value["identity_score"],
            value["station_count"],
        ),
        reverse=True,
    ):
        relation = item["candidate"].get("relation", {}) or {}
        tags = relation.get("tags", {}) or {}
        role = class_map.get(item["relation_id"], "filtered")
        print(
            f"  Relation {relation.get('id')} | "
            f"role={role} | "
            f"identity={item['identity_score']:.0f} | "
            f"stops={item['station_count']} | "
            f"matched={item['matched_count']} | "
            f"coverage={item['coverage']:.1%} | "
            f"name={tags.get('name', '')}"
        )

    # 有官方 YAML 时仍保留原来的安全门槛；但比较对象已经变成 Main。
    if official and best["coverage"] < 0.60:
        print(
            f"Relation 主路线站点覆盖不足: "
            f"{best['matched_count']}/{len(official)} "
            f"({best['coverage']:.1%})，回退 OSM 站点匹配。"
        )
        return None

    merged, merged_match_count, merged_match_score, inserted_count = _merge_relation_with_official(
        official,
        best["records"],
    )

    if len(merged) < 2:
        return None

    # Route Master 自身不是一条几何线；create_route 需要一个线性 stations
    # 兼容对象，因此仍把 Main 作为默认 stations。Branch / Partial 全部
    # 保存在 line._route_master 中，供后续 geometry/export 使用。
    return {
        "candidate": best["candidate"],
        "relation_name": best["relation_name"],
        "relation_id": best["relation_id"],
        "stations": merged,
        "matched_count": merged_match_count,
        "matched_score": merged_match_score,
        "coverage": best["coverage"],
        "identity_score": best["identity_score"],
        "inserted_count": inserted_count,
        "reversed": best["reverse"],
        "candidate_count": len(candidates),
        "route_master": route_master,
    }


# ---------------------------------------------------------------------------
# Fallback station path
# ---------------------------------------------------------------------------


def _fallback_stations(
    city_name: str,
    line_name: str,
    bbox: Sequence[float],
    official_stations: Sequence[Any],
) -> List[Any]:
    try:
        osm_stations = get_line_stations(city_name, line_name, bbox)
    except TypeError:
        try:
            osm_stations = get_line_stations(
                city=city_name,
                line=line_name,
                bbox=bbox,
            )
        except Exception as exc:
            print(f"OSM站点匹配失败: {exc}")
            osm_stations = []
    except Exception as exc:
        print(f"OSM站点匹配失败: {exc}")
        osm_stations = []

    if osm_stations:
        return list(osm_stations)

    # OSM 匹配失败时保留 YAML 官方站点，避免线路对象被错误清空。
    return list(official_stations)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_route(
    city_name: str,
    line_name: str,
    bbox: Sequence[float],
) -> Any:
    """
    创建线路对象。

    站点优先级：
        1. OSM Relation stop sequence
        2. YAML 官方站名用于命名/校验
        3. 现有 get_line_stations() 作为回退
    """
    city_name = _clean_text(city_name)
    line_name = _clean_text(line_name)

    official_stations = _official_stations(city_name, line_name)
    print(f"官方站点数量: {len(official_stations)}")

    line = _make_line(city_name, line_name)

    relation_result = _discover_stations_from_relation(
        city_name,
        line_name,
        bbox,
        official_stations,
    )

    final_stations: List[Any] = []

    if relation_result is not None:
        merged_records = relation_result["stations"]
        for order, record in enumerate(merged_records):
            name = _clean_text(record.get("name"))
            if not name:
                continue
            final_stations.append(
                _make_station(
                    name,
                    record.get("point"),
                    order,
                )
            )

        try:
            line._station_source = "osm_relation"
            line._relation_id = relation_result["relation_id"]
            line._relation_name = relation_result["relation_name"]
            line._relation_station_inserted = relation_result["inserted_count"]
            line._relation_station_match_count = relation_result["matched_count"]
            line._relation_station_coverage = relation_result["coverage"]
            line._relation_identity_score = relation_result["identity_score"]
            line._relation_reversed = relation_result["reversed"]
            line._route_master = relation_result.get("route_master")
            if line._route_master:
                line._route_master_type = line._route_master.get("type")
                line._route_master_main_id = line._route_master.get("main", {}).get("relation_id")
                line._route_master_main_pair = line._route_master.get("main_pair")
                line._route_master_main_pair_quality = line._route_master.get("main_pair_quality")
                line._route_master_quality = line._route_master.get("quality")
                line._route_master_branch_ids = [
                    item.get("relation_id")
                    for item in line._route_master.get("branches", [])
                ]
                line._route_master_partial_ids = [
                    item.get("relation_id")
                    for item in line._route_master.get("partials", [])
                ]
                line._route_master_variant_ids = [
                    item.get("relation_id")
                    for item in line._route_master.get("variants", [])
                ]
        except Exception:
            pass

        print(
            f"Relation 站点自动发现: "
            f"{len(final_stations)} 站 | "
            f"匹配官方={relation_result['matched_count']} | "
            f"自动补站={relation_result['inserted_count']} | "
            f"coverage={relation_result['coverage']:.1%}"
        )

    else:
        fallback = _fallback_stations(
            city_name,
            line_name,
            bbox,
            official_stations,
        )

        for order, station in enumerate(fallback):
            name = _station_name(station)
            if not name:
                continue
            final_stations.append(
                _make_station(
                    name,
                    _station_point(station),
                    order,
                )
            )

        try:
            line._station_source = "legacy_station_match"
        except Exception:
            pass

        print(f"回退站点数量: {len(final_stations)}")

    try:
        line.stations = final_stations
    except Exception:
        pass

    # 几何留给 geometry/route_builder.py。
    try:
        if not getattr(line, "geometry", None):
            line.geometry = []
    except Exception:
        pass

    print(f"最终站点数量: {len(final_stations)}")
    return line


def build_route(
    city_name: str,
    line_name: str,
    bbox: Sequence[float],
) -> Any:
    """create_route 的兼容别名。"""
    return create_route(city_name, line_name, bbox)


# 常见旧调用兼容。
build_line = create_route
parse_route = create_route
