from metrogis.api.track import (
    get_track_geometry
)



def test_tianjin_track():


    tracks = get_track_geometry(

        (
            38.8,
            116.8,
            39.4,
            117.8
        )

    )


    print()

    print(
        "轨迹数量:",
        len(tracks)
    )


    for item in tracks[:3]:

        print(
            item["id"],
            len(item["geometry"])
        )


    assert len(tracks) > 0
