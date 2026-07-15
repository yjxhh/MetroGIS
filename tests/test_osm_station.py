from metrogis.api.station import get_osm_stations



def test_find_zhangxingzhuang():


    stations = get_osm_stations(
        (
            38.8,
            116.8,
            39.4,
            117.8
        )
    )


    found = []


    for station in stations:

        name = station.get(
            "name",
            ""
        )


        if "张" in name:

            found.append(
                station
            )


    print()


    print(
        "找到:",
        len(found)
    )


    for item in found:

        print(
            item
        )