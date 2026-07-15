from metrogis.resources.loader import get_station_list
from metrogis.api.station import get_line_stations



def test_tianjin_line3_station_match():


    official = get_station_list(
        "天津",
        "3号线"
    )


    stations = get_line_stations(
        "天津",
        "3号线",
        (
            38.8,
            116.8,
            39.4,
            117.8
        )
    )


    matched = [
        s["official_name"]
        for s in stations
    ]


    missing = []


    for name in official:

        if name not in matched:

            missing.append(
                name
            )


    print()


    print(
        "官方:",
        len(official)
    )


    print(
        "匹配:",
        len(stations)
    )


    print(
        "缺失:",
        missing
    )


    assert len(missing) == 0