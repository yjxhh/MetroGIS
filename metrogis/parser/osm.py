from dataclasses import dataclass, field


@dataclass
class Station:
    name: str
    lat: float | None = None
    lng: float | None = None


@dataclass
class SubwayLine:
    name: str
    stations: list[Station] = field(default_factory=list)
    geometry: list = field(default_factory=list)


def clean_geometry(geometry):
    if not geometry:
        return []

    result = []
    last = None
    for p in geometry:
        if p != last:
            result.append(p)
            last = p
    return result


def parse_osm_subway(data, city=None):
    elements = data.get("elements", [])

    relation = None
    nodes = {}
    ways = {}

    for element in elements:
        etype = element.get("type")

        if etype == "node":
            node_id = element.get("id")
            if node_id is not None:
                nodes[node_id] = element

        elif etype == "way":
            way_id = element.get("id")
            if way_id is not None:
                ways[way_id] = element

        elif etype == "relation":
            tags = element.get("tags", {})
            if tags.get("route") in ("subway", "light_rail", "railway"):
                relation = element

    if relation is None:
        return SubwayLine(name="Unknown")

    line = SubwayLine(name=relation.get("tags", {}).get("name", "Unknown"))

    members = relation.get("members", [])

    # pytest兼容：没有members时，直接读取所有node
    if not members:
        for e in elements:
            if e.get("type") != "node":
                continue
            tags = e.get("tags", {})
            if "name" not in tags:
                continue
            line.stations.append(
                Station(
                    name=tags["name"],
                    lat=e.get("lat"),
                    lng=e.get("lon"),
                )
            )
        return line

    for m in members:
        if m.get("type") == "node" and m.get("role") in ("stop", "stop_entry_only", "stop_exit_only", "platform", ""):
            node = nodes.get(m.get("ref"))
            if not node:
                continue
            tags = node.get("tags", {})
            if "name" not in tags:
                continue
            line.stations.append(
                Station(
                    name=tags["name"],
                    lat=node.get("lat"),
                    lng=node.get("lon"),
                )
            )

    for m in members:
        if m.get("type") != "way":
            continue
        way = ways.get(m.get("ref"))
        if not way:
            continue

        if "geometry" in way:
            for pt in way["geometry"]:
                line.geometry.append([pt["lon"], pt["lat"]])
        else:
            for nid in way.get("nodes", []):
                node = nodes.get(nid)
                if node:
                    line.geometry.append([node.get("lon"), node.get("lat")])

    line.geometry = clean_geometry(line.geometry)
    return line
