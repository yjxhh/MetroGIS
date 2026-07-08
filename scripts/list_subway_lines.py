"""
列出 OSM 中所有包含关键字的轨道线路
"""

from metrogis.api.overpass import query_overpass



def main():

    query = """

    [out:json][timeout:90];


    relation

    ["route"="subway"]

    ["name"~"13",i];


    out tags;

    """


    data = query_overpass(
        query
    )


    print(
        "\n发现线路:\n"
    )


    for item in data.get(
        "elements",
        []
    ):

        tags = item.get(
            "tags",
            {}
        )


        print(
            item.get("id"),
            "=>",
            tags.get(
                "name",
                "UNKNOWN"
            )
        )



if __name__ == "__main__":

    main()
