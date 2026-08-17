"""HTTP client for the Grand Lyon data pusher API (Velo'v stations)."""

from __future__ import annotations

import math
import time
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


_client = httpx.Client(timeout=30.0, headers={"User-Agent": "velov-assistant/0.1"})


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get_json(url: str, params: dict[str, Any] | None = None) -> dict:
    return _client.get(url, params=params).raise_for_status().json()


_STATIONS_TTL = 30.0
_stations_cache: dict[str, Any] = {"ts": 0.0, "stations": []}


def get_stations() -> list[dict[str, Any]]:
    """Fetch the real-time station snapshot, cached for a short TTL."""
    now = time.monotonic()
    if now - _stations_cache["ts"] < _STATIONS_TTL and _stations_cache["stations"]:
        return _stations_cache["stations"]
    data = _get_json(settings.grandlyon_stations_url, params={"maxfeatures": -1})
    stations = [
        {**{k: row.get(k) for k in _STATION_KEYS}, "electrical_bikes": _electrical_bikes(row)} for row in data.get("values", [])
    ]
    _stations_cache.update(ts=now, stations=stations)
    return stations


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
    ranked = sorted(
        ({**s, "distance_m": round(_haversine(lat, lng, s["lat"], s["lng"]) * 1000)} for s in get_stations()),
        key=lambda s: s["distance_m"],
    )
    return ranked[:n]


def geocode(place: str) -> tuple[float, float] | None:
    """Geocode a free-text place using the Grand Lyon Photon geocoder."""
    data = _get_json(settings.photon_geocode_url, params={"q": place, "limit": 1})
    if not (features := data.get("features")):
        return None
    lon, lat = features[0]["geometry"]["coordinates"]
    return lat, lon
