"""dlt pipeline: load real-time Velo'v station data (optional helper pipeline).

The primary station data is fetched on-demand by app/tools/grandlyon.py. This
pipeline optionally snapshots the stations into DuckDB for historical analysis.
"""

from __future__ import annotations

import os

import dlt
from dlt.sources.helpers import requests

STATIONS_URL = os.getenv(
    "GRANDLYON_STATIONS_URL",
    "https://data.grandlyon.com/fr/datapusher/ws/rdata/jcd_jcdecaux.jcdvelov/all.json",
)
_KEYS = (
    "number",
    "name",
    "commune",
    "address",
    "lat",
    "lng",
    "status",
    "available_bikes",
    "available_bike_stands",
    "bike_stands",
    "last_update",
)


@dlt.resource(name="stations", primary_key="number", write_disposition="merge")
def stations_resource():
    """Stream station rows from the Grand Lyon datapusher API."""
    page = requests.get(STATIONS_URL, params={"maxfeatures": -1})
    page.raise_for_status()
    yield from ({k: row.get(k) for k in _KEYS} for row in page.json().get("values", []))


def run() -> None:
    """Snapshot stations into DuckDB (default)."""
    pipeline = dlt.pipeline(pipeline_name="velov_stations", destination="duckdb", dataset_name="stations")
    print(pipeline.run(stations_resource()))


if __name__ == "__main__":
    run()
