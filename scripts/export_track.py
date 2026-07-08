"""
导出指定区间线路轨迹 Excel

九里 -> 大医三院

每50米一个点

运行:

python -m scripts.export_track
"""


import json

from pathlib import Path

from shapely.geometry import (
    LineString,
    Point
)

from pyproj import Transformer

from openpyxl import Workbook



INPUT = "data/dalian_line13.geojson"


OUTPUT = "data/13号线#1.xlsx"


START = "九里"


END = "大医三院"


DISTANCE = 50



def main():

    with open(
        INPUT,
        encoding="utf-8"
    ) as f:

        data=json.load(f)



    line_coords=[]

    stations={}



    for feature in data["features"]:


        geom=feature["geometry"]


        if geom["type"]=="LineString":

            line_coords=geom["coordinates"]


        elif geom["type"]=="Point":

            name=feature["properties"]["name"]

            stations[name]=geom["coordinates"]



    print(
        "站点:",
        list(stations.keys())
    )



    to_meter = Transformer.from_crs(
        4326,
        32651,
        always_xy=True
    )


    to_wgs84 = Transformer.from_crs(
        32651,
        4326,
        always_xy=True
    )



    meter_coords=[]


    for lng,lat in line_coords:

        meter_coords.append(

            to_meter.transform(
                lng,
                lat
            )

        )



    line=LineString(
        meter_coords
    )



    start_point=Point(

        to_meter.transform(
            *stations[START]
        )

    )


    end_point=Point(

        to_meter.transform(
            *stations[END]
        )

    )



    start_distance=line.project(
        start_point
    )


    end_distance=line.project(
        end_point
    )



    reverse=False



    if start_distance>end_distance:

        reverse=True

        start_distance,end_distance=end_distance,start_distance



    print(
        "区间长度:",
        round(
            end_distance-start_distance
        ),
        "米"
    )



    points=[]


    distance=start_distance



    while distance<=end_distance:


        p=line.interpolate(
            distance
        )


        lng,lat=to_wgs84.transform(
            p.x,
            p.y
        )


        points.append(
            [
                round(lng,8),
                round(lat,8)
            ]
        )


        distance+=DISTANCE



    # 加入终点

    p=line.interpolate(
        end_distance
    )


    lng,lat=to_wgs84.transform(
        p.x,
        p.y
    )


    points.append(

        [
            round(lng,8),
            round(lat,8)
        ]

    )



    # 如果线路方向相反

    if reverse:

        points.reverse()



    wb=Workbook()


    ws=wb.active


    ws.title="13号线轨迹"



    ws.append(

        [
            "名称",
            "经度",
            "纬度"
        ]

    )



    for i,(lng,lat) in enumerate(points,1):


        ws.append(

            [

                f"13号线#{i}",

                lng,

                lat

            ]

        )



    for col in ws.columns:


        width=max(

            len(
                str(cell.value)
            )
            for cell in col

            if cell.value

        )


        ws.column_dimensions[
            col[0].column_letter
        ].width=width+3



    Path(
        OUTPUT
    ).parent.mkdir(
        exist_ok=True
    )


    wb.save(
        OUTPUT
    )



    print(
        "完成:",
        OUTPUT
    )


    print(
        "轨迹点:",
        len(points)
    )



if __name__=="__main__":

    main()