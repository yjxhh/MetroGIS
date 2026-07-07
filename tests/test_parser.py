from metrogis.parser.subway import parse_subway_line


def test_parse_subway_line():

    mock_data = {

        "elements": [

            {
                "type": "relation",
                "tags": {
                    "route": "subway",
                    "name": "大连地铁13号线"
                }
            },


            {
                "type": "node",
                "lat": 39.0,
                "lon": 121.8,
                "tags": {
                    "railway": "station",
                    "name": "九里"
                }
            }

        ]

    }


    result = parse_subway_line(
        mock_data
    )


    assert result["line"] == "大连地铁13号线"

    assert len(
        result["stations"]
    ) == 1
