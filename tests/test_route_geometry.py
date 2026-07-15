from metrogis.resources.loader import (
    get_station_list
)

from metrogis.parser.route_builder import (
    create_route
)

from metrogis.geometry.route_builder import (
    build_route_geometry
)



def test_tianjin_line3_geometry():


    line = create_route(
        "天津",
        "3号线",
        (
            38.8,
            116.8,
            39.4,
            117.8
        )
    )


    line = build_route_geometry(
        line,
        (
            38.8,
            116.8,
            39.4,
            117.8
        )
    )


    print()

    print(
        "站点:",
        len(line.stations)
    )


    print(
        "轨迹点:",
        len(line.geometry)
    )


    assert len(line.geometry) > 0
