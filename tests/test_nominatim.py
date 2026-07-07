from metrogis.api.nominatim import search_place


def test_search():

    result = search_place(
        "大医三院站 大连"
    )

    assert result is not None

    assert "lat" in result

    assert "lon" in result
