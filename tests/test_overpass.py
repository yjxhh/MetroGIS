from metrogis.api.overpass import search_metro_line


def test_line():

    data = search_metro_line(
        "13"
    )

    assert "elements" in data