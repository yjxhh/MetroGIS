"""
MetroGIS GeoJSON Exporter

负责将 MetroGIS 标准数据
转换为 GeoJSON 格式
"""

import json


def subway_to_geojson(subway_data: dict):
    """
    将地铁数据转换为 GeoJSON

    参数:
        subway_data:
            {
                "line": "线路名称",
                "stations": [
                    {
                        "name": "",
                        "lat": 0,
                        "lng": 0
                    }
                ]
            }

    返回:
        GeoJSON FeatureCollection
    """

    features = []


    for station in subway_data.get(
        "stations",
        []
    ):

        lat = station.get("lat")
        lng = station.get("lng")


        # 无坐标跳过
        if lat is None or lng is None:
            continue


        feature = {

            "type": "Feature",

            "geometry": {

                "type": "Point",

                "coordinates": [
                    lng,
                    lat
                ]

            },

            "properties": {

                "name": station.get(
                    "name"
                ),

                "line": subway_data.get(
                    "line"
                )

            }

        }


        features.append(
            feature
        )


    return {

        "type": "FeatureCollection",

        "features": features

    }



def save_geojson(data: dict, filename: str):
    """
    保存 GeoJSON 文件
    """

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )
