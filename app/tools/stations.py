"""Function-calling tools for real-time Velo'v station data."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from app.tools import grandlyon


def get_station_availability(
    station_name_or_location: Annotated[
        str, Field(description="A station name, address, or a place/landmark in Lyon (e.g. 'Part-Dieu').")
    ],
) -> dict[str, Any]:
    """Get real-time availability (bikes and free stands) for Velo'v stations. Accepts either a station name/address, or a place/landmark in Lyon — in which case it returns the nearest stations to that location."""
    q = station_name_or_location.lower()
    stations = grandlyon.get_stations()
    matches = [s for s in stations if any(q in (s.get(k) or "").lower() for k in ("name", "address", "commune", "pole"))]
    if not matches:
        if not (coords := grandlyon.geocode(station_name_or_location)):
            return {"query": station_name_or_location, "error": f"Could not locate '{station_name_or_location}'"}
        matches = grandlyon.nearest_stations(*coords, n=5)
    return {"query": station_name_or_location, "stations": matches[:10]}
