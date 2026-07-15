"""
MetroGIS Download Command

下载指定城市地铁线路，
解析 OSM，
导出 GeoJSON。
"""

from pathlib import Path

from metrogis.api.overpass import (
    search_metro_line
)

from metrogis.parser.osm import (
    parse_osm_subway
)

from metrogis.exporter.geojson import (
    subway_to_geojson,
    save_geojson
)


def remove_duplicate_stations(line):
    """
    去除重复站点。

    OSM 有些线路会同时包含
    上下行 stop，
    因此按照站名去重，
    保留第一次出现。
    """

    seen = set()

    result = []

    for station in line.stations:

        if station.name in seen:

            continue

        seen.add(
            station.name
        )

        result.append(
            station
        )

    line.stations = result

    return line


def build_output_filename(
    city,
    line
):
    """
    生成输出文件名

    示例：

    data/北京_10号线.geojson
    """

    filename = (
        f"{city}_{line}"
        ".geojson"
    )

    return str(

        Path("data")

        / filename

    )


def print_summary(line):
    """
    打印线路信息
    """

    print()

    print(
        "Line:",
        line.name
    )

    print(
        "Stations:",
        len(
            line.stations
        )
    )

    print(
        "Geometry:",
        len(
            line.geometry
        )
    )

    print()
def download_command(
    city: str,
    line: str
):
    """
    下载指定城市地铁线路

    Parameters
    ----------
    city
        城市名称

    line
        线路名称
    """

    print(
        f"Downloading {city} {line}..."
    )

    # 查询 Overpass

    data = search_metro_line(

        line_name=line,

        city=city

    )

    print(
        "Parse OSM data..."
    )

    # 解析 OSM

    subway = parse_osm_subway(

        data,

        city=city

    )

    print(
        "Before stations:",
        len(subway.stations)
    )

    # 去除重复站点

    subway = remove_duplicate_stations(
        subway
    )

    # 输出信息

    print_summary(
        subway
    )

    # 导出 GeoJSON

    geojson = subway_to_geojson(
        subway
    )

    output = build_output_filename(
        city,
        line
    )

    save_geojson(
        geojson,
        output
    )

    print(
        "Done:",
        output
    )

    return subway