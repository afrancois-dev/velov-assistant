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
            "description": (
                "Find the nearest Velo'v stations to a location with the number of available bikes and free stands at each."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "Latitude in degrees."},
                    "longitude": {"type": "number", "description": "Longitude in degrees."},
                },
                "required": ["latitude", "longitude"],
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


def find_nearest_bikes(latitude: float, longitude: float) -> dict[str, Any]:
    """Return the nearest stations with availability."""
    return {"latitude": latitude, "longitude": longitude, "stations": grandlyon.nearest_stations(latitude, longitude)}


TOOL_IMPL = {
    "get_station_availability": get_station_availability,
    "find_nearest_bikes": find_nearest_bikes,
}
