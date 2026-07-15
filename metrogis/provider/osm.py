"""
MetroGIS OSM Provider

负责从 OpenStreetMap 获取线路轨迹数据

"""



from metrogis.api.track import (
    get_track_geometry
)



def get_osm_geometry(
    bbox
):
    """
    获取 OSM 轨迹


    参数:

        bbox:
        (
            south,
            west,
            north,
            east
        )


    返回:

    [
        [
            lng,
            lat
        ],
        ...
    ]

    """


    tracks = get_track_geometry(
        bbox
    )


    geometry = []


    for track in tracks:


        points = track.get(
            "geometry",
            []
        )


        if not points:

            continue



        geometry.append(
            {
                "id":
                    track.get(
                        "id"
                    ),

                "geometry":
                    points
            }
        )


    return geometry





def get_osm_track_count(
    bbox
):
    """
    获取 OSM 轨迹数量

    用于调试
    """


    tracks = get_osm_geometry(
        bbox
    )


    return len(
        tracks
    )





def get_osm_lines(
    bbox
):
    """
    Provider统一接口

    返回线路geometry
    """


    return get_osm_geometry(
        bbox
    )