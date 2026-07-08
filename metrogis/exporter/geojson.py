"""
GeoJSON exporter
"""


import json

from pathlib import Path




def subway_to_geojson(
    line
):


    features = []



    # 兼容旧测试 dict

    if isinstance(
        line,
        dict
    ):


        line_name = line.get(
            "line",
            ""
        )


        stations = line.get(
            "stations",
            []
        )


        geometry = []


    else:


        line_name = line.name


        stations = line.stations


        geometry = line.geometry



    # LineString

    if geometry:


        features.append(

            {

                "type":"Feature",

                "geometry":{

                    "type":"LineString",

                    "coordinates":geometry

                },

                "properties":{

                    "name":line_name

                }

            }

        )



    # stations

    for station in stations:


        if isinstance(
            station,
            dict
        ):

            name = station.get(
                "name"
            )

            lat = station.get(
                "lat"
            )

            lng = station.get(
                "lng"
            )


        else:

            name = station.name

            lat = station.lat

            lng = station.lng



        features.append(

            {

                "type":"Feature",

                "geometry":{

                    "type":"Point",

                    "coordinates":[

                        lng,

                        lat

                    ]

                },

                "properties":{

                    "name":name,

                    "line":line_name

                }

            }

        )



    return {

        "type":"FeatureCollection",

        "features":features

    }




def save_geojson(
    data,
    filename
):


    path = Path(
        filename
    )


    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(

        path,

        "w",

        encoding="utf-8"

    ) as f:


        json.dump(

            data,

            f,

            ensure_ascii=False,

            indent=2

        )