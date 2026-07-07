import requests


OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"


def query_overpass(query: str):

    headers = {
        "User-Agent": "MetroGIS/0.1"
    }

    try:

        response = requests.post(
            OVERPASS_URL,
            data={
                "data": query
            },
            headers=headers,
            timeout=20
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:

        return {
            "elements": []
        }



def search_metro_line(line_name: str):

    query = f"""
    [out:json][timeout:10];

    relation
    ["route"="subway"]
    ["name"~"{line_name}",i];

    out tags;
    """

    return query_overpass(query)