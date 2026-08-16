"""HTTP client for the Grand Lyon data pusher API (Velo'v stations)."""

from __future__ import annotations

import math
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

_STATION_KEYS = (
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
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get_json(url: str, params: dict[str, Any] | None = None) -> dict:
    return (
        httpx.Client(timeout=30.0, headers={"User-Agent": "velov-assistant/0.1"})
        .get(url, params=params)
        .raise_for_status()
        .json()
    )


def get_stations() -> list[dict[str, Any]]:
    """Fetch the full real-time station snapshot (name, coords, availability)."""
    data = _get_json(settings.grandlyon_stations_url, params={"maxfeatures": -1})
    return [
        {**{k: row.get(k) for k in _STATION_KEYS}, "electrical_bikes": _electrical_bikes(row)} for row in data.get("values", [])
    ]


def _electrical_bikes(row: dict[str, Any]) -> int | None:
    return ((row.get("main_stands") or {}).get("availabilities") or {}).get("electricalBikes")


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def nearest_stations(lat: float, lng: float, n: int = 5) -> list[dict[str, Any]]:
    """Return the n nearest stations to a point, with distance in meters."""
    stations = get_stations()
    for s in stations:
        s["distance_m"] = round(_haversine(lat, lng, s["lat"], s["lng"]) * 1000)
    return sorted(stations, key=lambda s: s["distance_m"])[:n]


def geocode(place: str) -> tuple[float, float] | None:
    """Geocode a free-text place using the Grand Lyon Photon geocoder."""
    data = _get_json("https://download.data.grandlyon.com/geocoding/photon-bal/api", params={"q": place, "limit": 1})
    if not (features := data.get("features")):
        return None
    lon, lat = features[0]["geometry"]["coordinates"]
    return lat, lon
