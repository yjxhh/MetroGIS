from metrogis.parser.route_builder import (
    create_route
)



def test_tianjin_line3_route():


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


    print()

    print(
        "线路:",
        line.name
    )


    print(
        "站点:",
        len(line.stations)
    )


    for station in line.stations:

        print(
            station.sequence,
            station.name,
            station.lat,
            station.lng
        )


    assert len(line.stations) == 22
