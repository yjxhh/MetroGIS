"""
MetroGIS Resource Loader

读取中国轨道线路数据库

china_metro.yaml

"""

from pathlib import Path
import yaml



RESOURCE_FILE = Path(
    __file__
).parent / "china_metro.yaml"




def load_metro_database():
    """
    加载全国地铁数据库
    """

    with open(
        RESOURCE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = yaml.safe_load(
            f
        )


    return data





def get_city(
    city_name: str
):
    """
    获取城市数据
    """

    data = load_metro_database()


    cities = data.get(
        "cities",
        {}
    )


    return cities.get(
        city_name
    )





def get_line(
    city_name: str,
    line_name: str
):
    """
    获取指定线路


    示例:

    天津
    3号线

    """

    city = get_city(
        city_name
    )


    if city is None:

        return None



    lines = city.get(
        "lines",
        {}
    )


    return lines.get(
        line_name
    )





def get_station_list(
    city_name: str,
    line_name: str
):
    """
    获取运营站点顺序
    """

    line = get_line(
        city_name,
        line_name
    )


    if line is None:

        return []



    return line.get(
        "stations",
        []
    )