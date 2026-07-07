from metrogis.exporter.geojson import subway_to_geojson


def test_subway_to_geojson():

    subway = {

        "line": "大连地铁13号线",

        "stations": [

            {
                "name": "九里",
                "lat": 39.0,
                "lng": 121.8
            }

        ]

    }


    geojson = subway_to_geojson(
        subway
    )


    assert geojson["type"] == "FeatureCollection"

    assert len(
        geojson["features"]
    ) == 1


    feature = geojson["features"][0]


    assert feature["geometry"]["type"] == "Point"

    assert feature["properties"]["name"] == "九里"
