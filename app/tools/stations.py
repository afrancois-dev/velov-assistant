"""Function-calling tools for real-time Velo'v station data."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from app.tools import grandlyon


def get_station_availability(
    station_name_or_location: Annotated[str, Field(description="A station name (e.g. 'Part-Dieu') or a place/address in Lyon.")],
) -> dict[str, Any]:
    """Get real-time availability (bikes and free stands) for Velo'v stations matching a station name, address or place in Lyon."""
    q = station_name_or_location.lower()
    stations = grandlyon.get_stations()
    matches = [s for s in stations if any(q in (s.get(k) or "").lower() for k in ("name", "address", "commune", "pole"))]
    if not matches and (coords := grandlyon.geocode(station_name_or_location)):
        matches = grandlyon.nearest_stations(*coords, n=5)
    return {"query": station_name_or_location, "stations": matches[:10]}


def find_nearest_bikes(
    place: Annotated[str, Field(description="A place, landmark or address in Lyon (e.g. 'Part-Dieu station').")],
) -> dict[str, Any]:
    """Geocode a place and return the nearest stations with available bikes."""
    if not (coords := grandlyon.geocode(place)):
        return {"place": place, "error": f"Could not locate '{place}'"}
    return {"place": place, "latitude": coords[0], "longitude": coords[1], "stations": grandlyon.nearest_stations(*coords)}
