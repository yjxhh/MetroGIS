from metrogis.config import settings


def test_config():

    assert settings.get(
        "geometry",
        "interpolate_distance"
    ) == 50
