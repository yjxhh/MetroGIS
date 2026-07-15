from metrogis.resources.override import (
    get_override_station
)



def test_override():


    station = get_override_station(
        "天津",
        "3号线",
        "张兴庄"
    )


    print(
        station
    )


    assert station is not None