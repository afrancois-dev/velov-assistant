"""Function-calling tools for real-time Velo'v station data."""

from __future__ import annotations

from typing import Any

from app.tools import grandlyon

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_station_availability",
            "description": (
                "Get real-time availability (bikes and free stands) for Velo'v stations "
                "matching a station name, address or place in Lyon."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "station_name_or_location": {
                        "type": "string",
                        "description": "A station name (e.g. 'Part-Dieu') or a place/address in Lyon.",
                    }
                },
                "required": ["station_name_or_location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_nearest_bikes",
            "description": ("Find the nearest Velo'v stations with available bikes to a place, landmark or address in Lyon."),
            "parameters": {
                "type": "object",
                "properties": {
                    "place": {
                        "type": "string",
                        "description": "A place, landmark or address in Lyon (e.g. 'Part-Dieu station').",
                    }
                },
                "required": ["place"],
            },
        },
    },
]


def get_station_availability(station_name_or_location: str) -> dict[str, Any]:
    """Return stations whose name/address/commune/pole matches the given text."""
    q = station_name_or_location.lower()
    stations = grandlyon.get_stations()
    matches = [s for s in stations if any(q in (s.get(k) or "").lower() for k in ("name", "address", "commune", "pole"))]
    if not matches and (coords := grandlyon.geocode(station_name_or_location)):
        matches = grandlyon.nearest_stations(*coords, n=5)
    return {"query": station_name_or_location, "stations": matches[:10]}


def find_nearest_bikes(place: str) -> dict[str, Any]:
    """Geocode a place and return the nearest stations with availability."""
    if not (coords := grandlyon.geocode(place)):
        return {"place": place, "error": f"Could not locate '{place}'"}
    return {"place": place, "latitude": coords[0], "longitude": coords[1], "stations": grandlyon.nearest_stations(*coords)}


TOOL_IMPL = {
    "get_station_availability": get_station_availability,
    "find_nearest_bikes": find_nearest_bikes,
}
