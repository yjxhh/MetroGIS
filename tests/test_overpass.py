import pytest

pytestmark = pytest.mark.integration

from metrogis.api.overpass import search_metro_line


def test_line():

    data = search_metro_line(
        "13",
        (
            38.8,
            116.8,
            39.4,
            117.8,
        )
    )

    assert "elements" in data