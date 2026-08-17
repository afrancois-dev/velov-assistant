"""Function-calling tools for real-time Velo'v station data."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from app.tools import grandlyon

_STATION_FIELDS = (
    "number",
    "name",
    "address",
    "commune",
    "pole",
    "lat",
    "lng",
    "status",
    "available_bikes",
    "available_bike_stands",
    "bike_stands",
    "last_update",
    "electrical_bikes",
)


def _pick(station: dict[str, Any]) -> dict[str, Any]:
    out = {k: station.get(k) for k in _STATION_FIELDS}
    if "distance_m" in station:
        out["distance_m"] = station["distance_m"]
    return out


def geocode_place(
    place: Annotated[str, Field(description="A place, address or landmark in Lyon (e.g. 'Part-Dieu').")],
) -> dict[str, Any]:
    """Geocode a free-text place into lat/lng coordinates via the Grand Lyon Photon geocoder."""
    coords = grandlyon.geocode(place)
    if not coords:
        return {"place": place, "error": f"Could not locate '{place}'"}
    return {"place": place, "lat": coords[0], "lng": coords[1]}


def stations_by_name(
    name: Annotated[str, Field(description="A station name, address, commune or pole to match (substring).")],
    limit: Annotated[int, Field(description="Maximum number of stations to return.")] = 5,
) -> list[dict[str, Any]]:
    """Find Velo'v stations whose name/address/commune/pole matches a substring, with real-time availability."""
    q = name.lower()
    matches = [
        s for s in grandlyon.get_stations() if any(q in (s.get(k) or "").lower() for k in ("name", "address", "commune", "pole"))
    ]
    return [_pick(s) for s in matches[:limit]]


def stations_nearby(
    lat: Annotated[float, Field(description="Latitude of the point.")],
    lng: Annotated[float, Field(description="Longitude of the point.")],
    n: Annotated[int, Field(description="Maximum number of stations to return.")] = 5,
) -> list[dict[str, Any]]:
    """Return the n nearest Velo'v stations to a point, with distance in meters and real-time availability."""
    return [_pick(s) for s in grandlyon.nearest_stations(lat, lng, n=n)]


def get_station_availability(
    station_name_or_location: Annotated[
        str, Field(description="A station name, address, or a place/landmark in Lyon (e.g. 'Part-Dieu').")
    ],
) -> dict[str, Any]:
    """Get real-time availability (bikes and free stands) for Velo'v stations. Accepts either a station name/address, or a place/landmark in Lyon — in which case it returns the nearest stations."""
    by_name = stations_by_name(station_name_or_location, limit=10)
    if by_name:
        return {"query": station_name_or_location, "stations": by_name}
    coords = grandlyon.geocode(station_name_or_location)
    if not coords:
        return {"query": station_name_or_location, "error": f"Could not locate '{station_name_or_location}'"}
    return {"query": station_name_or_location, "stations": stations_nearby(*coords, n=5)}
