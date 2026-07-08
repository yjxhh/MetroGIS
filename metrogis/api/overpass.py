"""
MetroGIS Overpass API

负责从 OpenStreetMap Overpass API
获取地铁/轻轨/快轨线路数据
"""

import time
import requests


OVERPASS_SERVERS = [

    "https://overpass-api.de/api/interpreter",

    "https://overpass.kumi.systems/api/interpreter",

    "https://overpass.private.coffee/api/interpreter"

]


def query_overpass(
    query: str,
    retry: int = 3
):

    last_error = None


    for server in OVERPASS_SERVERS:


        for index in range(retry):

            try:

                print(
                    f"Query Overpass: {server}"
                )


                response = requests.post(

                    server,

                    data={
                        "data": query
                    },

                    headers={
                        "User-Agent":
                        "MetroGIS/0.1"
                    },

                    timeout=180

                )


                response.raise_for_status()


                return response.json()



            except Exception as e:


                last_error = e


                print(
                    f"failed {index + 1}/{retry}: {e}"
                )


                time.sleep(3)



    raise RuntimeError(
        last_error
    )



def search_metro_line(
    line_name: str,
    city: str = "大连"
):

    """
    查询指定城市地铁线路

    支持：
    地铁
    轻轨
    快轨

    """


    # 大连范围 bbox
    #
    # south,west,north,east
    #

    bbox = (
        "38.7,"
        "120.9,"
        "39.6,"
        "122.1"
    )



    query = f"""

    [out:json][timeout:180];


    (
    
    relation

    ["route"="subway"]

    ["name"~"{line_name}"]

    ({bbox});


    relation

    ["route"="light_rail"]

    ["name"~"{line_name}"]

    ({bbox});


    relation

    ["route"="railway"]

    ["name"~"{line_name}"]

    ({bbox});


    );


    out body;


    >;


    out geom;


    """



    data = query_overpass(
        query
    )


    print(
        "Elements:",
        len(
            data.get(
                "elements",
                []
            )
        )
    )


    return data