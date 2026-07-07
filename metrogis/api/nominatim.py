import requests


NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


def search_place(name):

    queries = [
        name,
        name.replace("站", ""),
        f"{name} 大连"
    ]

    headers = {
        "User-Agent": "MetroGIS/0.2.0"
    }


    for query in queries:

        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }


        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=30
        )


        response.raise_for_status()

        data = response.json()


        if data:

            item = data[0]

            return {
                "name": item["display_name"],
                "lat": float(item["lat"]),
                "lon": float(item["lon"])
            }


    return None
