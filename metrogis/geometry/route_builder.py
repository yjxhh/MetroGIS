"""
MetroGIS route geometry builder V10.1

Core change from V9.x:
1. Relation Way geometry is the authoritative route geometry source.
2. Way members are topologically re-ordered by endpoint connectivity instead of
   blindly using Relation member order.
3. No A* / shortest-path over the union of Relation Ways for the primary path.
4. Station positions are projected onto the ordered Relation polyline and the
   geometry is sliced between the first and last Relation stops.
5. A reversed Relation can be used automatically when its stop/geometry order
   is opposite to the project's official station order.
6. Missing/unnamed Relation stop names do not automatically invalidate a valid
   geometry candidate.
"""

from __future__ import annotations

import inspect
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import re

from pyproj import Geod

from metrogis.api.overpass import get_line_relation_tracks
from metrogis.parser.station_matcher import station_name_score


geod = Geod(ellps="WGS84")


# ---------------------------------------------------------------------------
# Generic object helpers
# ---------------------------------------------------------------------------


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    """Read a value from either a dict-like or object-like model."""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _clean_name(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_point(value: Any) -> Optional[Tuple[float, float]]:
    """Normalize a point to (lon, lat)."""
    if value is None:
        return None

    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None

    lon = _get(value, "lon", "lng", "longitude")
    lat = _get(value, "lat", "latitude")
    if lon is None or lat is None:
        return None
    try:
        return float(lon), float(lat)
    except (TypeError, ValueError):
        return None


def _station_name(station: Any) -> str:
    return _clean_name(_get(station, "name", "station_name", "title", default=""))


def _station_point(station: Any) -> Optional[Tuple[float, float]]:
    point = _get(station, "point", "geometry", "coordinate", "coordinates")
    parsed = _as_point(point)
    if parsed is not None:
        return parsed

    # MetroGIS's current Station models commonly expose lat/lng directly.
    # Geometry integration must support those objects as well as point-based
    # records returned by OSM/older code.
    lat = _get(station, "lat", "latitude", default=None)
    lng = _get(station, "lng", "lon", "longitude", default=None)
    if lat is None or lng is None:
        return None
    return _as_point([lng, lat])


def _line_context(line: Any) -> Tuple[str, str, Optional[str]]:
    """Extract city, line name and optional ref from a Line model."""

    city = _clean_name(
        _get(line, "city_name", "city", "cityname", default="")
    )
    name = _clean_name(
        _get(line, "line_name", "route_name", "name", default="")
    )
    ref = _get(line, "line_ref", "ref", "route_ref", default=None)
    ref = _clean_name(ref) or None

    # The parser currently uses IDs like 天津_3号线 and names like 天津3号线.
    line_id = _clean_name(_get(line, "id", "line_id", default=""))
    if line_id and "_" in line_id:
        id_city, id_name = line_id.split("_", 1)
        if not city:
            city = id_city
        if not name:
            name = id_name

    if not city and name:
        # No safe general city parser is possible here, so leave name intact.
        # Overpass matching still has the bounding box as a hard spatial limit.
        pass

    if city and name.startswith(city):
        name = name[len(city) :].strip()

    return city, name, ref


# ---------------------------------------------------------------------------
# Geodesic helpers
# ---------------------------------------------------------------------------


def point_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """WGS84 geodesic distance in meters."""
    if a is None or b is None:
        return float("inf")
    _, _, dist = geod.inv(float(a[0]), float(a[1]), float(b[0]), float(b[1]))
    return float(dist)


def geometry_length(geometry: Sequence[Sequence[float]]) -> float:
    if not geometry or len(geometry) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(geometry[:-1], geometry[1:]):
        total += point_distance(a, b)
    return total


def _interpolate_point(a: Sequence[float], b: Sequence[float], t: float) -> Tuple[float, float]:
    """Interpolate a point in lon/lat; segments are short OSM way segments."""
    t = max(0.0, min(1.0, float(t)))
    return (
        float(a[0]) + (float(b[0]) - float(a[0])) * t,
        float(a[1]) + (float(b[1]) - float(a[1])) * t,
    )


def _project_to_segment(
    point: Sequence[float],
    a: Sequence[float],
    b: Sequence[float],
) -> Tuple[float, Tuple[float, float], float]:
    """Project point to a short lon/lat segment and return t, projected point, distance."""
    # A local equirectangular projection is sufficient for finding the closest
    # point on individual OSM segments. Distances themselves are always Geod.
    lat0 = math.radians((float(a[1]) + float(b[1]) + float(point[1])) / 3.0)
    scale_x = 111320.0 * max(0.01, math.cos(lat0))
    scale_y = 110540.0

    ax = float(a[0]) * scale_x
    ay = float(a[1]) * scale_y
    bx = float(b[0]) * scale_x
    by = float(b[1]) * scale_y
    px = float(point[0]) * scale_x
    py = float(point[1]) * scale_y

    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        proj = (float(a[0]), float(a[1]))
        return 0.0, proj, point_distance(point, proj)

    t = ((px - ax) * dx + (py - ay) * dy) / denom
    t = max(0.0, min(1.0, t))
    proj = _interpolate_point(a, b, t)
    return t, proj, point_distance(point, proj)


def _point_to_polyline(
    point: Sequence[float],
    geometry: Sequence[Sequence[float]],
    start_segment: int = 0,
) -> Tuple[float, Tuple[float, float], float, int, float]:
    """Return cumulative position, projected point, distance, segment index, t."""
    if not geometry:
        return 0.0, (float(point[0]), float(point[1])), float("inf"), 0, 0.0
    if len(geometry) == 1:
        p = _as_point(geometry[0])
        assert p is not None
        return 0.0, p, point_distance(point, p), 0, 0.0

    start_segment = max(0, min(start_segment, len(geometry) - 2))

    cumulative = 0.0
    best = (float("inf"), (0.0, 0.0), 0, 0.0, 0.0)

    # Compute cumulative length once while scanning.
    for i in range(len(geometry) - 1):
        a = geometry[i]
        b = geometry[i + 1]
        seg_len = point_distance(a, b)

        if i >= start_segment:
            t, proj, dist = _project_to_segment(point, a, b)
            if dist < best[0]:
                best = (dist, proj, i, t, cumulative + seg_len * t)

        cumulative += seg_len

    return best[4], best[1], best[0], best[2], best[3]


def _slice_polyline(
    geometry: Sequence[Sequence[float]],
    start_pos: float,
    end_pos: float,
) -> List[List[float]]:
    """Slice a polyline by cumulative geodesic distance."""
    if not geometry:
        return []

    total = geometry_length(geometry)
    if total <= 0.0:
        p = _as_point(geometry[0])
        return [list(p)] if p else []

    if start_pos > end_pos:
        reversed_geom = [list(p) for p in reversed(geometry)]
        return _slice_polyline(reversed_geom, total - end_pos, total - start_pos)

    start_pos = max(0.0, min(total, start_pos))
    end_pos = max(0.0, min(total, end_pos))

    out: List[List[float]] = []
    cumulative = 0.0

    def append_point(p: Sequence[float]) -> None:
        q = [float(p[0]), float(p[1])]
        if not out or point_distance(out[-1], q) > 0.001:
            out.append(q)

    # Start projection.
    if start_pos <= 1e-6:
        append_point(geometry[0])
    else:
        for i in range(len(geometry) - 1):
            a = geometry[i]
            b = geometry[i + 1]
            seg_len = point_distance(a, b)
            if cumulative + seg_len >= start_pos:
                t = 0.0 if seg_len <= 1e-9 else (start_pos - cumulative) / seg_len
                append_point(_interpolate_point(a, b, t))
                break
            cumulative += seg_len

    # Original vertices between the two positions.
    cumulative = 0.0
    for i in range(1, len(geometry)):
        cumulative += point_distance(geometry[i - 1], geometry[i])
        if cumulative > start_pos + 1e-6 and cumulative < end_pos - 1e-6:
            append_point(geometry[i])

    # End projection.
    if end_pos >= total - 1e-6:
        append_point(geometry[-1])
    else:
        cumulative = 0.0
        for i in range(len(geometry) - 1):
            a = geometry[i]
            b = geometry[i + 1]
            seg_len = point_distance(a, b)
            if cumulative + seg_len >= end_pos:
                t = 0.0 if seg_len <= 1e-9 else (end_pos - cumulative) / seg_len
                append_point(_interpolate_point(a, b, t))
                break
            cumulative += seg_len

    return out


# ---------------------------------------------------------------------------
# Relation / Way helpers
# ---------------------------------------------------------------------------


def _way_id(way: Dict[str, Any]) -> Optional[int]:
    value = way.get("id", way.get("way_id", way.get("osm_id")))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _way_nodes(way: Dict[str, Any]) -> List[int]:
    raw = way.get("nodes", way.get("node_ids", [])) or []
    out: List[int] = []
    for value in raw:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


def _way_geometry(way: Dict[str, Any]) -> List[List[float]]:
    raw = way.get("geometry", []) or []
    out: List[List[float]] = []
    for value in raw:
        point = _as_point(value)
        if point is not None:
            out.append([point[0], point[1]])
    return out


def _relation_members(relation: Dict[str, Any]) -> List[Dict[str, Any]]:
    members = relation.get("members", []) or []
    return [m for m in members if isinstance(m, dict) and m.get("type") == "way"]


def _member_index_by_way_id(relation: Dict[str, Any]) -> Dict[int, int]:
    result: Dict[int, int] = {}
    for i, member in enumerate(_relation_members(relation)):
        try:
            wid = int(member.get("ref"))
        except (TypeError, ValueError):
            continue
        result[wid] = i
    return result


def _find_first_way(
    ways: List[Dict[str, Any]],
    first_stop_id: Optional[int],
    first_stop_point: Optional[Tuple[float, float]],
    member_index: Dict[int, int],
) -> Optional[int]:
    """Choose the way containing/closest to the first Relation stop."""
    best: Optional[Tuple[float, int, int]] = None

    for pos, way in enumerate(ways):
        wid = _way_id(way)
        if wid is None:
            continue
        nodes = _way_nodes(way)
        geom = _way_geometry(way)
        if len(geom) < 2:
            continue

        if first_stop_id is not None and first_stop_id in nodes:
            distance = 0.0
            exact_rank = 0
        elif first_stop_point is not None:
            _, _, distance, _, _ = _point_to_polyline(first_stop_point, geom)
            exact_rank = 1
        else:
            distance = float(member_index.get(wid, 10**9))
            exact_rank = 2

        key = (distance, exact_rank, member_index.get(wid, 10**9))
        if best is None or key < best:
            best = (distance, exact_rank, member_index.get(wid, 10**9))
            best_pos = pos

    return best_pos if best is not None else None


def _orient_way(
    way: Dict[str, Any],
    start_node: Optional[int] = None,
    reference_point: Optional[Tuple[float, float]] = None,
) -> Tuple[List[int], List[List[float]]]:
    nodes = _way_nodes(way)
    geom = _way_geometry(way)
    if not nodes or len(geom) < 2:
        return nodes, geom

    reverse = False
    if start_node is not None:
        if nodes[0] == start_node:
            reverse = False
        elif nodes[-1] == start_node:
            reverse = True
    elif reference_point is not None:
        d_first = point_distance(reference_point, geom[0])
        d_last = point_distance(reference_point, geom[-1])
        reverse = d_last < d_first

    if reverse:
        return list(reversed(nodes)), [list(p) for p in reversed(geom)]
    return list(nodes), [list(p) for p in geom]


def _endpoint_distance(
    point: Sequence[float],
    endpoint: Sequence[float],
) -> float:
    return point_distance(point, endpoint)


def build_ordered_relation_chain(
    candidate: Dict[str, Any],
    connect_tolerance: float = 25.0,
    start_point: Optional[Tuple[float, float]] = None,
    start_node_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Reconstruct a single ordered polyline from Relation Ways.

    The Relation member order is only used as a tie-breaker. Connectivity of
    actual Way endpoints is authoritative. This handles OSM relations where a
    few Way members have been re-ordered but still form a continuous track.
    """

    relation = candidate.get("relation", {}) or {}
    tracks = list(candidate.get("tracks", []) or [])
    member_index = _member_index_by_way_id(relation)

    ways: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for track in tracks:
        wid = _way_id(track)
        if wid is None or wid in seen:
            continue
        if len(_way_nodes(track)) < 2 or len(_way_geometry(track)) < 2:
            continue
        seen.add(wid)
        ways.append(track)

    stops = list(candidate.get("stops", []) or [])
    first_stop = stops[0] if stops else None
    first_stop_id = start_node_id
    if first_stop_id is None and first_stop is not None:
        raw_id = _get(first_stop, "id", "node_id", "ref", default=None)
        try:
            first_stop_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            first_stop_id = None

    first_stop_point = start_point
    if first_stop_point is None and first_stop is not None:
        first_stop_point = _station_point(first_stop)
    if first_stop_point is None and first_stop is not None:
        lat = _get(first_stop, "lat", "latitude", default=None)
        lon = _get(first_stop, "lon", "lng", "longitude", default=None)
        first_stop_point = _as_point([lon, lat]) if lat is not None and lon is not None else None

    if not ways:
        return {
            "geometry": [],
            "way_ids": [],
            "used_way_count": 0,
            "total_way_count": 0,
            "connected": False,
            "continuous": False,
            "length": 0.0,
        }

    first_pos = _find_first_way(ways, first_stop_id, first_stop_point, member_index)
    if first_pos is None:
        return {
            "geometry": [],
            "way_ids": [],
            "used_way_count": 0,
            "total_way_count": len(ways),
            "connected": False,
            "continuous": False,
            "length": 0.0,
        }

    unused: Dict[int, Dict[str, Any]] = {}
    for way in ways:
        wid = _way_id(way)
        if wid is not None:
            unused[wid] = way

    first_way = ways[first_pos]
    first_wid = _way_id(first_way)
    assert first_wid is not None

    nodes, geom = _orient_way(first_way, reference_point=first_stop_point)
    if not nodes or len(geom) < 2:
        return {
            "geometry": [],
            "way_ids": [],
            "used_way_count": 0,
            "total_way_count": len(ways),
            "connected": False,
            "continuous": False,
            "length": 0.0,
        }

    del unused[first_wid]

    ordered_ids = [first_wid]
    chain: List[List[float]] = [list(p) for p in geom]
    current_node = nodes[-1]
    current_point = chain[-1]
    previous_member_index = member_index.get(first_wid, 0)

    while unused:
        best: Optional[Tuple[float, int, int, Dict[str, Any], List[int], List[List[float]]]] = None

        # 1) Prefer exact OSM node connectivity.
        for wid, way in unused.items():
            wn = _way_nodes(way)
            wg = _way_geometry(way)
            if len(wn) < 2 or len(wg) < 2:
                continue

            if wn[0] == current_node:
                oriented_nodes, oriented_geom = _orient_way(way, start_node=current_node)
                connect_dist = 0.0
            elif wn[-1] == current_node:
                oriented_nodes, oriented_geom = _orient_way(way, start_node=current_node)
                connect_dist = 0.0
            else:
                continue

            midx = member_index.get(wid, 10**9)
            target_distance = 0.0
            if stops:
                last_point = _station_point(stops[-1])
                if last_point is not None:
                    target_distance = min(
                        point_distance(last_point, oriented_geom[0]),
                        point_distance(last_point, oriented_geom[-1]),
                    )
            score = connect_dist + target_distance * 0.001 + abs(midx - previous_member_index) * 0.05
            item = (score, 0, midx, way, oriented_nodes, oriented_geom)
            if best is None or item[:3] < best[:3]:
                best = item

        # 2) If the OSM node IDs do not connect, permit a small geometric gap.
        if best is None:
            for wid, way in unused.items():
                wn = _way_nodes(way)
                wg = _way_geometry(way)
                if len(wn) < 2 or len(wg) < 2:
                    continue

                d_first = _endpoint_distance(current_point, wg[0])
                d_last = _endpoint_distance(current_point, wg[-1])
                connect_dist = min(d_first, d_last)
                if connect_dist > connect_tolerance:
                    continue

                oriented_nodes, oriented_geom = _orient_way(
                    way,
                    reference_point=current_point,
                )
                midx = member_index.get(wid, 10**9)
                target_distance = 0.0
                if stops:
                    last_point = _station_point(stops[-1])
                    if last_point is not None:
                        target_distance = min(
                            point_distance(last_point, oriented_geom[0]),
                            point_distance(last_point, oriented_geom[-1]),
                        )
                score = connect_dist + target_distance * 0.001 + abs(midx - previous_member_index) * 0.05
                item = (score, 1, midx, way, oriented_nodes, oriented_geom)
                if best is None or item[:3] < best[:3]:
                    best = item

        if best is None:
            break

        _, gap_rank, midx, way, oriented_nodes, oriented_geom = best
        wid = _way_id(way)
        assert wid is not None

        # For a small geometric gap, explicitly bridge it. This is only a
        # fallback for inconsistent OSM node IDs and is limited by tolerance.
        if gap_rank == 1 and chain:
            gap = point_distance(chain[-1], oriented_geom[0])
            if gap > 0.001:
                chain.append(list(oriented_geom[0]))

        for point in oriented_geom:
            if not chain or point_distance(chain[-1], point) > 0.001:
                chain.append(list(point))

        ordered_ids.append(wid)
        del unused[wid]
        current_node = oriented_nodes[-1]
        current_point = chain[-1]
        previous_member_index = midx

    used = len(ordered_ids)
    total = len(ways)

    return {
        "geometry": chain,
        "way_ids": ordered_ids,
        "used_way_count": used,
        "total_way_count": total,
        # connected means every Relation Way member was consumed.
        # continuous means the selected Way subset itself forms a joined chain.
        "connected": used == total,
        "continuous": used > 0,
        "length": geometry_length(chain),
    }


# ---------------------------------------------------------------------------
# Station / Relation scoring
# ---------------------------------------------------------------------------


def _relation_stop_id(stop: Any) -> Optional[int]:
    value = _get(stop, "id", "node_id", "ref", default=None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _relation_stop_point(stop: Any, stop_nodes: Optional[Dict[Any, Any]] = None) -> Optional[Tuple[float, float]]:
    point = _station_point(stop)
    if point is not None:
        return point

    sid = _relation_stop_id(stop)
    if sid is None or not stop_nodes:
        return None

    node = stop_nodes.get(sid) or stop_nodes.get(str(sid))
    if node is None:
        return None

    point = _station_point(node)
    if point is not None:
        return point

    lat = _get(node, "lat", "latitude", default=None)
    lon = _get(node, "lon", "lng", "longitude", default=None)
    if lat is not None and lon is not None:
        return _as_point([lon, lat])
    return None


def _relation_stop_name(stop: Any, stop_nodes: Optional[Dict[Any, Any]] = None) -> str:
    name = _station_name(stop)
    if name:
        return name

    sid = _relation_stop_id(stop)
    if sid is not None and stop_nodes:
        node = stop_nodes.get(sid) or stop_nodes.get(str(sid))
        if node is not None:
            return _station_name(node)
    return ""


def _sequence_match_score(
    official_names: Sequence[str],
    relation_names: Sequence[str],
) -> Tuple[int, float]:
    """Subsequence-style DP; extra OSM stops and unnamed stops are allowed."""
    n = len(official_names)
    m = len(relation_names)
    if n == 0 or m == 0:
        return 0, 0.0

    # dp[i][j] = (matched_count, total_name_score)
    dp: List[List[Tuple[int, float]]] = [
        [(0, 0.0) for _ in range(m + 1)] for _ in range(n + 1)
    ]

    for i in range(1, n + 1):
        dp[i][0] = (0, 0.0)
    for j in range(1, m + 1):
        dp[0][j] = (0, 0.0)

    def better(a: Tuple[int, float], b: Tuple[int, float]) -> Tuple[int, float]:
        if a[0] != b[0]:
            return a if a[0] > b[0] else b
        return a if a[1] >= b[1] else b

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = better(dp[i - 1][j], dp[i][j - 1])
            score = float(station_name_score(official_names[i - 1], relation_names[j - 1]))
            if score > 0:
                candidate = (dp[i - 1][j - 1][0] + 1, dp[i - 1][j - 1][1] + score)
                best = better(best, candidate)
            dp[i][j] = best

    return dp[n][m]


def _orient_relation_for_official_stations(
    relation_stops: Sequence[Any],
    stop_nodes: Optional[Dict[Any, Any]],
    official_stations: Sequence[Any],
) -> Tuple[List[Any], bool, int, float]:
    official_names = [_station_name(s) for s in official_stations]
    direct_names = [_relation_stop_name(s, stop_nodes) for s in relation_stops]
    reverse_names = list(reversed(direct_names))

    direct_count, direct_score = _sequence_match_score(official_names, direct_names)
    reverse_count, reverse_score = _sequence_match_score(official_names, reverse_names)

    if (reverse_count, reverse_score) > (direct_count, direct_score):
        return list(reversed(relation_stops)), True, reverse_count, reverse_score
    return list(relation_stops), False, direct_count, direct_score


def _official_first_last_names(official_stations: Sequence[Any]) -> Tuple[str, str]:
    names = [_station_name(s) for s in official_stations]
    if not names:
        return "", ""
    return names[0], names[-1]


def _normalize_station_key(value: Any) -> str:
    text = _clean_name(value)
    return " ".join(text.replace("站", "").split()).casefold()


def _candidate_stop_records(candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    stops = list(candidate.get("stops", []) or [])
    stop_nodes = candidate.get("stop_nodes", {}) or {}
    records: List[Dict[str, Any]] = []
    for stop in stops:
        records.append(
            {
                "name": _relation_stop_name(stop, stop_nodes),
                "point": _relation_stop_point(stop, stop_nodes),
                "raw": stop,
            }
        )
    return records


def _candidate_endpoint_point(
    candidate: Dict[str, Any],
    target_name: str,
) -> Optional[Tuple[float, float]]:
    target_key = _normalize_station_key(target_name)
    if not target_key:
        return None
    for record in _candidate_stop_records(candidate):
        if _normalize_station_key(record.get("name", "")) == target_key:
            point = record.get("point")
            if point is not None:
                return point
    return None


def _candidate_declared_endpoints(candidate: Dict[str, Any]) -> Tuple[str, str]:
    relation = candidate.get("relation", {}) or {}
    tags = relation.get("tags", {}) or {}
    from_name = _clean_name(tags.get("from", ""))
    to_name = _clean_name(tags.get("to", ""))
    if from_name or to_name:
        return from_name, to_name

    relation_name = _clean_name(tags.get("name", ""))
    match = re.search(r"[：:]\s*(.*?)\s*[→-]\s*(.*?)\s*$", relation_name)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return "", ""


def _orient_extension_chain(
    candidate: Dict[str, Any],
    chain_geometry: Sequence[Sequence[float]],
    target_name: str,
    anchor_name: str,
    side: str,
) -> List[List[float]]:
    """
    Orient an endpoint-evidence geometry so its missing terminal is on the
    requested side and the Main Relation anchor is the opposite boundary.

    Route Master completion intentionally records only the missing terminal name.
    At geometry time we reuse the same evidence Relation's authoritative Way
    geometry, then orient it from/to the target using Relation metadata and stop
    endpoints. No free-graph path is introduced.
    """
    geometry = [list(point) for point in chain_geometry]
    if len(geometry) < 2:
        return geometry

    declared_from, declared_to = _candidate_declared_endpoints(candidate)
    first_name = _relation_stop_name(
        (candidate.get("stops") or [None])[0],
        candidate.get("stop_nodes", {}) or {},
    ) if candidate.get("stops") else ""
    last_name = _relation_stop_name(
        (candidate.get("stops") or [None])[-1],
        candidate.get("stop_nodes", {}) or {},
    ) if candidate.get("stops") else ""

    target_key = _normalize_station_key(target_name)
    anchor_key = _normalize_station_key(anchor_name)

    # First use Relation from/to because V6.7-2.2.2 can legitimately have the
    # target terminal declared in metadata while it is absent from stop members.
    if side == "start":
        if _normalize_station_key(declared_from) == target_key:
            return geometry
        if _normalize_station_key(declared_to) == target_key:
            return list(reversed(geometry))
        if _normalize_station_key(last_name) == anchor_key:
            return geometry
        if _normalize_station_key(first_name) == anchor_key:
            return list(reversed(geometry))
    else:
        if _normalize_station_key(declared_to) == target_key:
            return geometry
        if _normalize_station_key(declared_from) == target_key:
            return list(reversed(geometry))
        if _normalize_station_key(first_name) == anchor_key:
            return geometry
        if _normalize_station_key(last_name) == anchor_key:
            return list(reversed(geometry))

    # Final fallback: compare the terminal point with any explicit target stop.
    target_point = _candidate_endpoint_point(candidate, target_name)
    if target_point is not None:
        first_distance = point_distance(target_point, geometry[0])
        last_distance = point_distance(target_point, geometry[-1])
        if side == "start":
            return geometry if first_distance <= last_distance else list(reversed(geometry))
        return list(reversed(geometry)) if first_distance <= last_distance else geometry

    return geometry


def _geometry_is_continuous(
    geometry: Sequence[Sequence[float]],
    max_gap: float = 25.0,
) -> bool:
    if not geometry or len(geometry) < 2:
        return False
    for point_a, point_b in zip(geometry[:-1], geometry[1:]):
        if point_distance(point_a, point_b) > max_gap:
            return False
    return True


def _slice_extension_to_anchor(
    geometry: Sequence[Sequence[float]],
    anchor_point: Optional[Tuple[float, float]],
    side: str,
) -> Tuple[List[List[float]], Optional[Tuple[float, float]]]:
    """
    Cut an evidence Relation chain at the Main Relation's observed endpoint.

    Returns the extension polyline and its target-side endpoint. The target-side
    endpoint is the chain endpoint after orientation, which is used to enrich
    the missing Route Master station coordinates.
    """
    if len(geometry) < 2:
        return [], None

    oriented = [list(point) for point in geometry]
    if anchor_point is None:
        target_point = _as_point(oriented[0] if side == "start" else oriented[-1])
        return oriented, target_point

    anchor_position, anchor_projection, _, _, _ = _point_to_polyline(
        anchor_point,
        oriented,
    )
    total = geometry_length(oriented)

    if side == "start":
        if anchor_position <= 0.0:
            return [], None
        extension = _slice_polyline(oriented, 0.0, anchor_position)
        target_point = _as_point(extension[0]) if extension else None
    else:
        if anchor_position >= total:
            return [], None
        extension = _slice_polyline(oriented, anchor_position, total)
        target_point = _as_point(extension[-1]) if extension else None

    return extension, target_point


def _set_station_point(
    station: Any,
    point: Optional[Sequence[float]],
) -> None:
    if point is None:
        return
    lon = float(point[0])
    lat = float(point[1])
    for attr, value in (
        ("lng", lon),
        ("lon", lon),
        ("longitude", lon),
        ("lat", lat),
        ("latitude", lat),
        ("point", [lon, lat]),
        ("coordinates", [lon, lat]),
    ):
        try:
            setattr(station, attr, value)
        except Exception:
            pass


def _route_master_completion(
    line: Any,
) -> Dict[str, Any]:
    master = _get(line, "_route_master", default=None) or {}
    completion = master.get("completion", {}) or {}
    return completion


def _find_candidate_by_relation_id(
    candidates: Sequence[Dict[str, Any]],
    relation_id: Any,
) -> Optional[Dict[str, Any]]:
    try:
        target_id = int(relation_id)
    except (TypeError, ValueError):
        target_id = relation_id

    for candidate in candidates:
        rid = (candidate.get("relation", {}) or {}).get("id")
        try:
            rid_normalized = int(rid)
        except (TypeError, ValueError):
            rid_normalized = rid
        if rid_normalized == target_id:
            return candidate
    return None


def _apply_route_master_endpoint_geometry_completion(
    line: Any,
    best: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extend Main Relation geometry with the exact Relation evidence used by
    V6.7-2.2.2 to recover missing terminals.

    This is deliberately conservative:
    - only the recorded start/end evidence Relation IDs are eligible;
    - only the segment from the evidence geometry to the Main observed endpoint
      is copied;
    - no union of arbitrary cohort Ways is performed.
    """
    completion = _route_master_completion(line).get("main", {}) or {}
    if not completion.get("added_count"):
        return {
            "geometry": list(best.get("geometry", []) or []),
            "start_added": False,
            "end_added": False,
            "start_relation_id": None,
            "end_relation_id": None,
            "start_point": None,
            "end_point": None,
        }

    geometry = [list(point) for point in (best.get("geometry", []) or [])]
    main_candidate = best.get("_candidate", best.get("candidate", {})) or {}
    main_records = _candidate_stop_records(main_candidate)
    if not main_records:
        return {
            "geometry": geometry,
            "start_added": False,
            "end_added": False,
            "start_relation_id": None,
            "end_relation_id": None,
            "start_point": None,
            "end_point": None,
        }

    main_start_point = next(
        (item["point"] for item in main_records if item.get("point") is not None),
        None,
    )
    main_end_point = next(
        (item["point"] for item in reversed(main_records) if item.get("point") is not None),
        None,
    )
    main_start_name = main_records[0].get("name", "")
    main_end_name = main_records[-1].get("name", "")

    metadata = {
        "geometry": geometry,
        "start_added": False,
        "end_added": False,
        "start_relation_id": None,
        "end_relation_id": None,
        "start_point": None,
        "end_point": None,
    }

    start_ids = list(completion.get("start_evidence_relation_ids", []) or [])
    end_ids = list(completion.get("end_evidence_relation_ids", []) or [])

    if start_ids:
        candidate = _find_candidate_by_relation_id(candidates, start_ids[0])
        if candidate is not None:
            chain_info = build_ordered_relation_chain(candidate)
            chain = _orient_extension_chain(
                candidate,
                chain_info.get("geometry", []) or [],
                completion.get("declared_start", ""),
                main_start_name,
                "start",
            )
            extension, target_point = _slice_extension_to_anchor(
                chain,
                main_start_point,
                "start",
            )
            if len(extension) >= 2 and geometry:
                metadata["start_added"] = True
                metadata["start_relation_id"] = start_ids[0]
                metadata["start_point"] = target_point
                anchor = extension[-1]
                if point_distance(anchor, geometry[0]) > 1.0:
                    extension = extension + [list(geometry[0])]
                metadata["geometry"] = extension[:-1] + geometry
            elif len(extension) >= 2 and not geometry:
                metadata["start_added"] = True
                metadata["start_relation_id"] = start_ids[0]
                metadata["start_point"] = target_point
                metadata["geometry"] = extension

    if end_ids:
        candidate = _find_candidate_by_relation_id(candidates, end_ids[0])
        if candidate is not None:
            chain_info = build_ordered_relation_chain(candidate)
            chain = _orient_extension_chain(
                candidate,
                chain_info.get("geometry", []) or [],
                completion.get("declared_end", ""),
                main_end_name,
                "end",
            )
            extension, target_point = _slice_extension_to_anchor(
                chain,
                main_end_point,
                "end",
            )
            if len(extension) >= 2 and metadata["geometry"]:
                metadata["end_added"] = True
                metadata["end_relation_id"] = end_ids[0]
                metadata["end_point"] = target_point
                anchor = extension[0]
                if point_distance(metadata["geometry"][-1], anchor) > 1.0:
                    metadata["geometry"].append(list(anchor))
                metadata["geometry"].extend(extension[1:])
            elif len(extension) >= 2:
                metadata["end_added"] = True
                metadata["end_relation_id"] = end_ids[0]
                metadata["end_point"] = target_point
                metadata["geometry"] = extension

    return metadata


def _station_sequence_positions(
    stations: Sequence[Any],
    geometry: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    """
    Project the final Line.stations sequence onto the rebuilt Relation polyline.

    V6.7-3 uses the already-completed station sequence from Route Master as the
    geometry reference, so endpoint completion is reflected in the final slice
    instead of silently trimming back to the raw Relation stop sequence.
    """
    if not stations or len(geometry) < 2:
        return {
            "positions": [],
            "snap_sum": 0.0,
            "max_snap": 0.0,
            "monotonic_failures": 0,
            "projected_count": 0,
        }

    positions: List[float] = []
    snap_sum = 0.0
    max_snap = 0.0
    previous_segment = 0
    monotonic_failures = 0

    for station in stations:
        point = _station_point(station)
        if point is None:
            continue

        position, _, snap, segment_idx, _ = _point_to_polyline(
            point,
            geometry,
            start_segment=previous_segment,
        )

        if positions and position + 50.0 < positions[-1]:
            retry_position, _, retry_snap, retry_segment, _ = _point_to_polyline(
                point,
                geometry,
                start_segment=0,
            )
            if retry_position >= positions[-1] - 50.0:
                position = retry_position
                snap = retry_snap
                segment_idx = retry_segment
            else:
                monotonic_failures += 1

        positions.append(position)
        previous_segment = max(previous_segment, segment_idx)
        snap_sum += snap
        max_snap = max(max_snap, snap)

    return {
        "positions": positions,
        "snap_sum": snap_sum,
        "max_snap": max_snap,
        "monotonic_failures": monotonic_failures,
        "projected_count": len(positions),
    }


# ---------------------------------------------------------------------------
# Relation candidate evaluation / geometry
# ---------------------------------------------------------------------------


def evaluate_relation_candidate(
    candidate: Dict[str, Any],
    route_stations: Sequence[Any],
) -> Optional[Dict[str, Any]]:
    relation = candidate.get("relation", {}) or {}
    relation_id = relation.get("id")
    relation_name = _clean_name(relation.get("tags", {}).get("name", relation.get("name", "")))
    stops = list(candidate.get("stops", []) or [])
    stop_nodes = candidate.get("stop_nodes", {}) or {}

    if len(stops) < 2:
        return None

    # V6.7-3: the completed Route Master station sequence is the geometry
    # boundary. When an endpoint was added by Route Master completion, start the
    # Way-chain from that completed endpoint rather than from the first raw
    # Relation stop.
    first_station_point = _station_point(route_stations[0]) if route_stations else None

    # Related Route Master records are dicts that retain the authoritative OSM
    # stop id as ``id``. Line.stations created by the parser normally expose
    # coordinates but do not retain that id. When the geometry stage is given a
    # Route Master role sequence, prefer that exact OSM node id so the Way-chain
    # starts from the correct station instead of merely choosing the nearest
    # geometry Way. This prevents short/disconnected sub-chains from being
    # selected when a different Way happens to be geographically closer.
    start_node_id = (
        _get(
            route_stations[0],
            "osm_node_id",
            "node_id",
            default=None,
        )
        if route_stations
        else None
    )

    if start_node_id is None and route_stations and isinstance(route_stations[0], dict):
        start_node_id = _get(route_stations[0], "id", default=None)

        # Older Route Master records may keep the OSM stop member under raw.
        if start_node_id is None:
            raw_record = _get(route_stations[0], "raw", default=None)
            if isinstance(raw_record, dict):
                start_node_id = _get(
                    raw_record,
                    "id",
                    "node_id",
                    "ref",
                    default=None,
                )

    try:
        start_node_id = int(start_node_id) if start_node_id is not None else None
    except (TypeError, ValueError):
        start_node_id = None

    chain_info = build_ordered_relation_chain(
        candidate,
        start_point=first_station_point,
        start_node_id=start_node_id,
    )
    geometry = chain_info["geometry"]
    if len(geometry) < 2:
        return None

    oriented_stops, reversed_relation, matched_count, matched_score = _orient_relation_for_official_stations(
        stops,
        stop_nodes,
        route_stations,
    )

    # The chain itself is constructed from the final station direction. If the
    # Relation stop sequence is opposite to the final station order, reverse
    # the resulting geometry as well.
    oriented_geometry = list(reversed(geometry)) if reversed_relation else geometry

    # First prefer the complete Line.stations sequence for slicing and quality
    # checks. Fall back to Relation stops only when the Line stations do not
    # carry enough coordinates.
    station_projection = _station_sequence_positions(
        route_stations,
        oriented_geometry,
    )

    if station_projection["projected_count"] >= 2:
        route_geometry = oriented_geometry
        projected_positions = station_projection["positions"]

        # The final station sequence is authoritative. Its first/last
        # projected positions must delimit the route in the same direction.
        start_pos = projected_positions[0]
        end_pos = projected_positions[-1]

        if end_pos < start_pos - 50.0:
            oriented_geometry = list(reversed(oriented_geometry))
            station_projection = _station_sequence_positions(
                route_stations,
                oriented_geometry,
            )
            projected_positions = station_projection["positions"]
            start_pos = projected_positions[0] if projected_positions else 0.0
            end_pos = projected_positions[-1] if projected_positions else 0.0
            reversed_relation = not reversed_relation

        if end_pos > start_pos + 1.0:
            route_geometry = _slice_polyline(oriented_geometry, start_pos, end_pos)
        else:
            route_geometry = oriented_geometry

        max_snap = station_projection["max_snap"]
        snap_sum = station_projection["snap_sum"]
        monotonic_failures = station_projection["monotonic_failures"]
        projected_count = station_projection["projected_count"]
    else:
        oriented_stop_points: List[Tuple[float, float]] = []
        for stop in oriented_stops:
            point = _relation_stop_point(stop, stop_nodes)
            if point is not None:
                oriented_stop_points.append(point)

        max_snap = 0.0
        snap_sum = 0.0
        previous_segment = 0
        monotonic_failures = 0
        positions: List[float] = []

        for stop_point in oriented_stop_points:
            position, _, snap, segment_idx, _ = _point_to_polyline(
                stop_point,
                oriented_geometry,
                start_segment=previous_segment,
            )
            if positions and position + 50.0 < positions[-1]:
                position2, _, snap2, segment2, _ = _point_to_polyline(
                    stop_point,
                    oriented_geometry,
                    start_segment=0,
                )
                if position2 >= positions[-1] - 50.0:
                    position = position2
                    snap = snap2
                    segment_idx = segment2
                else:
                    monotonic_failures += 1

            positions.append(position)
            previous_segment = max(previous_segment, segment_idx)
            snap_sum += snap
            max_snap = max(max_snap, snap)

        route_geometry = oriented_geometry
        if positions:
            start_pos = min(positions)
            end_pos = max(positions)
            if end_pos > start_pos + 1.0:
                route_geometry = _slice_polyline(oriented_geometry, start_pos, end_pos)

        projected_count = len(positions)

    route_length = geometry_length(route_geometry)

    coverage = (
        chain_info["used_way_count"] / chain_info["total_way_count"]
        if chain_info["total_way_count"]
        else 0.0
    )

    # Score favours Relation completeness and station sequence agreement, not
    # an external hard-coded line length. Route Master preference is applied
    # later by build_relation_route().
    score = (
        matched_score
        + matched_count * 20.0
        + coverage * 500.0
        - monotonic_failures * 500.0
        - max_snap * 2.0
    )

    return {
        "relation_id": relation_id,
        "relation_name": relation_name,
        # Keep the raw Relation candidate available to the geometry stage.
        # Route Master endpoint completion stores evidence by Relation ID;
        # Geometry must be able to retrieve that exact candidate without
        # re-querying or guessing which Way set produced the evaluation.
        "candidate": candidate,
        "chain": chain_info,
        "geometry": route_geometry,
        "length": route_length,
        "reversed": reversed_relation,
        "matched_count": matched_count,
        "matched_score": matched_score,
        "max_snap": max_snap,
        "snap_sum": snap_sum,
        "monotonic_failures": monotonic_failures,
        "projected_station_count": projected_count,
        "score": score,
        "stops": oriented_stops,
    }


def _call_get_line_relation_tracks(
    city_name: str,
    line_name: str,
    bbox: Sequence[float],
    line_ref: Optional[str],
) -> Dict[str, Any]:
    """Call the current Overpass API helper without assuming one exact signature."""
    func = get_line_relation_tracks
    params = inspect.signature(func).parameters

    kwargs: Dict[str, Any] = {}
    mapping = {
        "city": city_name,
        "city_name": city_name,
        "line": line_name,
        "line_name": line_name,
        "bbox": bbox,
        "line_ref": line_ref,
        "ref": line_ref,
        "route_ref": line_ref,
    }

    for name in params:
        if name in mapping and mapping[name] is not None:
            kwargs[name] = mapping[name]

    # Handle implementations with a required first positional argument whose
    # name was not anticipated above.
    try:
        return func(**kwargs)
    except TypeError as exc:
        # A conservative fallback for the signatures used by MetroGIS V4/V5.
        attempts = [
            ((city_name, line_name, bbox, line_ref), {}),
            ((line_name, bbox, line_ref, city_name), {}),
            ((line_name, bbox, line_ref), {}),
            ((line_name, bbox), {}),
        ]
        last_error: Exception = exc
        for args, extra_kwargs in attempts:
            try:
                return func(*args, **extra_kwargs)
            except TypeError as retry_exc:
                last_error = retry_exc
        raise last_error


def _build_related_route_geometries(
    line: Any,
    candidates: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build Geometry for Route Master Branch / Partial / Variant Relations.

    Main Geometry remains the canonical Line.geometry. Related geometries are
    kept separate so a branch or short-turn Relation cannot accidentally replace
    the Main route. Each relation is evaluated against its own Route Master
    station sequence rather than the complete Main station sequence.
    """
    master = _get(line, "_route_master", default=None) or {}
    candidate_map: Dict[Any, Dict[str, Any]] = {}

    for candidate in candidates:
        relation_id = (candidate.get("relation", {}) or {}).get("id")
        if relation_id is None:
            continue
        candidate_map[relation_id] = candidate
        try:
            candidate_map[int(relation_id)] = candidate
        except (TypeError, ValueError):
            pass

    results: Dict[str, List[Dict[str, Any]]] = {
        "branches": [],
        "partials": [],
        "variants": [],
    }

    for role in results:
        entries = list(master.get(role, []) or [])
        for entry in entries:
            relation_id = entry.get("relation_id")
            candidate = candidate_map.get(relation_id)
            if candidate is None:
                try:
                    candidate = candidate_map.get(int(relation_id))
                except (TypeError, ValueError):
                    candidate = None

            if candidate is None:
                continue

            station_records = list(entry.get("records", []) or [])
            evaluation = evaluate_relation_candidate(
                candidate,
                station_records,
            )
            if evaluation is None:
                continue

            chain = evaluation["chain"]
            geometry = list(evaluation.get("geometry", []) or [])
            results[role].append(
                {
                    "relation_id": evaluation["relation_id"],
                    "relation_name": evaluation["relation_name"],
                    "role": role,
                    "station_count": entry.get(
                        "station_count",
                        len(station_records),
                    ),
                    "start_station": (
                        station_records[0].get("name", "")
                        if station_records
                        else ""
                    ),
                    "end_station": (
                        station_records[-1].get("name", "")
                        if station_records
                        else ""
                    ),
                    "geometry": geometry,
                    "length": geometry_length(geometry),
                    "reversed": evaluation.get("reversed", False),
                    "way_ids": list(chain.get("way_ids", []) or []),
                    "used_way_count": chain.get("used_way_count", 0),
                    "total_way_count": chain.get("total_way_count", 0),
                    "way_chain_connected": chain.get("connected", False),
                    "way_chain_continuous": chain.get("continuous", False),
                    "way_coverage": (
                        chain.get("used_way_count", 0)
                        / chain.get("total_way_count", 1)
                        if chain.get("total_way_count", 0)
                        else 0.0
                    ),
                    "projected_station_count": evaluation.get(
                        "projected_station_count",
                        0,
                    ),
                    "max_snap": evaluation.get("max_snap", 0.0),
                    "snap_sum": evaluation.get("snap_sum", 0.0),
                    "station_monotonic_failures": evaluation.get(
                        "monotonic_failures",
                        0,
                    ),
                    "metrics": dict(entry.get("metrics", {}) or {}),
                }
            )

    return results


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_relation_route(
    line: Any,
    bbox: Sequence[float],
) -> Optional[Dict[str, Any]]:
    city_name, line_name, line_ref = _line_context(line)
    if not line_name:
        return None

    print("搜索线路 OSM Relation...")
    result = _call_get_line_relation_tracks(city_name, line_name, bbox, line_ref)
    candidates = list(result.get("candidates", []) or [])
    if not candidates:
        return None

    route_stations = list(_get(line, "stations", default=[]) or [])
    preferred_relation_id = _get(
        line,
        "_route_master_main_id",
        "_relation_id",
        default=None,
    )
    try:
        preferred_relation_id = int(preferred_relation_id) if preferred_relation_id is not None else None
    except (TypeError, ValueError):
        pass

    print(f"Relation 候选: {len(candidates)}")
    if preferred_relation_id is not None:
        print(f"Route Master Main Relation: {preferred_relation_id}")

    evaluated: List[Dict[str, Any]] = []
    for candidate in candidates:
        evaluation = evaluate_relation_candidate(candidate, route_stations)
        if evaluation is None:
            continue

        evaluation["route_master_preferred"] = (
            preferred_relation_id is not None
            and evaluation["relation_id"] == preferred_relation_id
        )

        print(
            f"  Relation {evaluation['relation_id']} | "
            f"role={'main' if evaluation['route_master_preferred'] else 'candidate'} | "
            f"ways={evaluation['chain']['used_way_count']}/{evaluation['chain']['total_way_count']} | "
            f"stops={len(evaluation['stops'])} | "
            f"匹配={evaluation['matched_count']}/{len(route_stations) if route_stations else '-'} | "
            f"长度={evaluation['length'] / 1000:.3f} km | "
            f"snap_max={evaluation['max_snap']:.1f}m | "
            f"projected_stations={evaluation.get('projected_station_count', 0)} | "
            f"reverse={evaluation['reversed']}"
        )
        evaluated.append(evaluation)

    if not evaluated:
        return None

    evaluated.sort(
        key=lambda x: (
            x["route_master_preferred"],
            x["score"],
            x["matched_count"],
            x["chain"]["used_way_count"],
        ),
        reverse=True,
    )
    best = evaluated[0]

    # V6.7-3: when Route Master completion added one or both terminals, extend
    # the selected Main geometry with the exact same evidence Relations used by
    # station completion. This keeps station and geometry evidence aligned.
    completion_geometry = _apply_route_master_endpoint_geometry_completion(
        line,
        best,
        candidates,
    )
    if completion_geometry.get("geometry"):
        best = dict(best)
        best["geometry"] = completion_geometry["geometry"]
        best["length"] = geometry_length(best["geometry"])
        best["endpoint_completion"] = completion_geometry

    best["related_geometries"] = _build_related_route_geometries(
        line,
        candidates,
    )

    print(
        f"选择 Relation {best['relation_id']} | "
        f"{best['relation_name']} | "
        f"Route Master Main={best['route_master_preferred']} | "
        f"{best['length'] / 1000:.3f} km"
    )

    if completion_geometry.get("start_added") or completion_geometry.get("end_added"):
        print(
            "  Geometry 端点补全: "
            f"start={'+' if completion_geometry.get('start_added') else '-'}"
            f"{completion_geometry.get('start_relation_id') or ''} | "
            f"end={'+' if completion_geometry.get('end_added') else '-'}"
            f"{completion_geometry.get('end_relation_id') or ''}"
        )

    return best


def build_route_geometry(
    line: Any,
    bbox: Sequence[float],
) -> Any:
    """Build and attach route geometry to a Line object."""

    relation_result = build_relation_route(line, bbox)
    if relation_result is None:
        print("Relation 路线重建失败，暂不使用自由图最短路，避免产生错误绕行几何。")
        return line

    geometry = [list(point) for point in (relation_result["geometry"] or [])]

    # V6.7-3: endpoint geometry completion can recover coordinates for the two
    # Route Master-added terminals. Populate those Station objects before the
    # final station projection pass.
    endpoint_completion = relation_result.get("endpoint_completion", {}) or {}
    if line.stations:
        if endpoint_completion.get("start_point") is not None:
            _set_station_point(line.stations[0], endpoint_completion["start_point"])
        if endpoint_completion.get("end_point") is not None:
            _set_station_point(line.stations[-1], endpoint_completion["end_point"])

    station_projection = _station_sequence_positions(
        line.stations,
        geometry,
    )

    line.geometry = geometry

    # Keep a few optional attributes populated when the Line model permits it.
    relation_chain = relation_result["chain"]
    # OSM geometry vertices within a Way can be sparse, so checking every
    # vertex distance would incorrectly flag a valid polyline. The Way-chain
    # builder already enforces exact-node or <=25m joins.
    geometry_continuous = bool(
        geometry
        and relation_chain.get(
            "continuous",
            relation_chain.get("connected", False),
        )
    )
    projected_count = station_projection.get(
        "projected_count",
        relation_result.get("projected_station_count", 0),
    )

    geometry_metadata = {
        "geometry_length": geometry_length(geometry),
        "route_length": geometry_length(geometry),
        "geometry_relation_id": relation_result["relation_id"],
        "geometry_relation_name": relation_result["relation_name"],
        "geometry_route_master_preferred": relation_result.get("route_master_preferred", False),
        "geometry_way_ids": list(relation_chain.get("way_ids", []) or []),
        "geometry_used_way_count": relation_chain.get("used_way_count", 0),
        "geometry_total_way_count": relation_chain.get("total_way_count", 0),
        # True means the selected final polyline has no gap larger than the
        # geometry continuity tolerance. It does not hide unused auxiliary
        # Relation Way members; those remain visible in way coverage.
        "geometry_connected": geometry_continuous,
        "geometry_way_chain_connected": relation_chain.get("connected", False),
        "geometry_chain_continuous": relation_chain.get("continuous", False),
        "geometry_way_coverage": (
            relation_chain.get("used_way_count", 0) / relation_chain.get("total_way_count", 1)
            if relation_chain.get("total_way_count", 0)
            else 0.0
        ),
        "geometry_projected_station_count": projected_count,
        "geometry_max_snap": station_projection.get("max_snap", relation_result.get("max_snap", 0.0)),
        "geometry_snap_sum": station_projection.get("snap_sum", relation_result.get("snap_sum", 0.0)),
        "geometry_station_monotonic_failures": station_projection.get(
            "monotonic_failures",
            relation_result.get("monotonic_failures", 0),
        ),
        "geometry_endpoint_completion_applied": bool(
            endpoint_completion.get("start_added") or endpoint_completion.get("end_added")
        ),
        "geometry_endpoint_completion_start_relation_id": endpoint_completion.get(
            "start_relation_id"
        ),
        "geometry_endpoint_completion_end_relation_id": endpoint_completion.get(
            "end_relation_id"
        ),
        "geometry_branch_count": len(
            relation_result.get("related_geometries", {}).get("branches", [])
        ),
        "geometry_partial_count": len(
            relation_result.get("related_geometries", {}).get("partials", [])
        ),
        "geometry_variant_count": len(
            relation_result.get("related_geometries", {}).get("variants", [])
        ),
    }

    if geometry:
        geometry_metadata["geometry_start"] = list(geometry[0])
        geometry_metadata["geometry_end"] = list(geometry[-1])

    for attr, value in geometry_metadata.items():
        try:
            setattr(line, attr, value)
        except Exception:
            pass

    related_geometries = relation_result.get("related_geometries", {}) or {}
    for attr, value in (
        ("geometry_branches", related_geometries.get("branches", [])),
        ("geometry_partials", related_geometries.get("partials", [])),
        ("geometry_variants", related_geometries.get("variants", [])),
        ("geometry_related_routes", related_geometries),
    ):
        try:
            setattr(line, attr, value)
        except Exception:
            pass

    print(f"最终 Relation 几何长度: {relation_result['length']:.2f} m")
    print(f"轨迹点: {len(geometry)}")
    return line


# Backward-compatible alias used by some callers.
create_route_geometry = build_route_geometry
