"""The single function-calling facade for real-time velo'v data."""

from __future__ import annotations

from typing import Annotated, Any, Literal

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


def _matches_filters(station: dict[str, Any], need_bikes: bool, need_free_stands: bool) -> bool:
    return (not need_bikes or (station.get("available_bikes") or 0) > 0) and (
        not need_free_stands or (station.get("available_bike_stands") or 0) > 0
    )


def _sort_key(station: dict[str, Any], sort_by: str) -> float:
    values = {
        "distance": station.get("distance_m"),
        "bikes": station.get("available_bikes"),
        "free_stands": station.get("available_bike_stands"),
    }
    return values[sort_by] if values[sort_by] is not None else float("inf")


def get_velov_info(
    location: Annotated[str, Field(description="A Velo'v station name, address or landmark in Lyon (e.g. 'Part-Dieu').")],
    radius_m: Annotated[int, Field(description="Search radius in meters.", ge=100, le=5000)] = 1000,
    limit: Annotated[int, Field(description="Maximum number of stations to return.", ge=1, le=20)] = 5,
    need_bikes: Annotated[bool, Field(description="Only return stations with available bikes.")] = False,
    need_free_stands: Annotated[bool, Field(description="Only return stations with free stands.")] = False,
    sort_by: Annotated[
        Literal["distance", "bikes", "free_stands"],
        Field(description="Sort by distance, available bikes, or free stands."),
    ] = "distance",
) -> dict[str, Any]:
    """Return live station availability by name or around a place.

    Matching and geocoding happen here so the model never handles raw
    coordinates or has to choose between several station tools.
    """
    query = location.strip()
    if not query:
        return {"query": location, "error": "A location is required", "stations": []}
    stations = grandlyon.get_stations()
    query_lower = query.lower()
    matches = [
        station
        for station in stations
        if any(query_lower in (station.get(field) or "").lower() for field in ("name", "address", "commune", "pole"))
    ]

    response: dict[str, Any] = {
        "query": query,
        "search": "station_match" if matches else "nearby",
        "radius_m": radius_m,
        "stations": [],
    }

    if matches:
        candidates = matches
    else:
        coords = grandlyon.geocode(query)
        if not coords:
            response["error"] = f"Could not locate '{query}'"
            return response
        response["location"] = {"lat": coords[0], "lng": coords[1]}
        candidates = [
            station
            for station in grandlyon.nearest_stations(*coords, n=len(stations))
            if station.get("distance_m", float("inf")) <= radius_m
        ]

    candidates = [station for station in candidates if _matches_filters(station, need_bikes, need_free_stands)]
    candidates.sort(key=lambda station: _sort_key(station, sort_by), reverse=sort_by in {"bikes", "free_stands"})
    response["stations"] = [_pick(station) for station in candidates[:limit]]
    return response
