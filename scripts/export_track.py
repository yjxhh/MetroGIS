"""
导出指定区间线路轨迹 Excel

大医三院 -> 九里

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

OUTPUT = "data/dayi_sanyuan_to_jiuli.xlsx"


START = "大医三院"

END = "九里"


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



    transformer_to_meter=Transformer.from_crs(
        4326,
        3857,
        always_xy=True
    )


    transformer_to_wgs84=Transformer.from_crs(
        3857,
        4326,
        always_xy=True
    )



    meter_coords=[]


    for lng,lat in line_coords:

        meter_coords.append(

            transformer_to_meter.transform(
                lng,
                lat
            )

        )



    line=LineString(
        meter_coords
    )



    start=Point(

        transformer_to_meter.transform(
            *stations[START]
        )

    )


    end=Point(

        transformer_to_meter.transform(
            *stations[END]
        )

    )



    start_distance=line.project(
        start
    )


    end_distance=line.project(
        end
    )



    if start_distance>end_distance:

        start_distance,end_distance=end_distance,start_distance



    length=end_distance-start_distance



    print(
        "线路长度:",
        round(length),
        "米"
    )



    wb=Workbook()


    ws=wb.active

    ws.title="13号线轨迹"



    ws.append(

        [
            "序号",
            "名称",
            "经度",
            "纬度"
        ]

    )



    index=1



    distance=start_distance



    while distance<=end_distance:


        point=line.interpolate(
            distance
        )


        lng,lat=transformer_to_wgs84.transform(

            point.x,

            point.y

        )


        ws.append(

            [

                index,

                f"13号线#{index}",

                round(lng,8),

                round(lat,8)

            ]

        )


        index+=1


        distance += DISTANCE



    # 确保终点加入

    point=line.interpolate(
        end_distance
    )


    lng,lat=transformer_to_wgs84.transform(
        point.x,
        point.y
    )


    ws.append(

        [

            index,

            f"13号线#{index}",

            round(lng,8),

            round(lat,8)

        ]

    )



    # 自动列宽

    for col in ws.columns:

        max_length=0

        for cell in col:

            if cell.value:

                max_length=max(
                    max_length,
                    len(str(cell.value))
                )


        ws.column_dimensions[
            col[0].column_letter
        ].width=max_length+3



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
        "点数量:",
        index
    )



if __name__=="__main__":

    main()