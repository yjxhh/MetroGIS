from metrogis.parser.osm import parse_osm_subway


def test_parse_osm_subway():

    data = {

        "elements": [

            {
                "type":"relation",
                "tags":{
                    "route":"subway",
                    "name":"大连地铁13号线"
                }
            },

            {
                "type":"node",
                "lat":39.1,
                "lon":121.7,
                "tags":{
                    "name":"九里"
                }
            }

        ]

    }


    line = parse_osm_subway(
        data
    )


    assert line.name == "大连地铁13号线"

    assert len(
        line.stations
    ) == 1

    assert line.stations[0].name == "九里"
