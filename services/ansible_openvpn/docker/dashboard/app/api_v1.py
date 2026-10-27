"""Sound level and recognition API mounted under /api/v1."""

from __future__ import annotations

import csv
import math
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

api_router = APIRouter()


# Settings
# --------

@dataclass(frozen=True)
# API settings loaded from the environment.
class Settings:
    api_key: str
    indicators_index: str
    events_index: str
    sensor_names_file: Optional[str]
    window_seconds: float


settings = Settings(
    api_key=os.getenv("R4E_API_KEY", ""),
    indicators_index=os.getenv("INDICATORS_INDEX", "sensor_indicators_*"),
    events_index=os.getenv("EVENTS_INDEX", "sensor_yamnet_*"),
    sensor_names_file=os.getenv("SENSOR_NAMES_FILE") or None,
    window_seconds=float(os.getenv("INDICATOR_WINDOW_SECONDS", "0.125")),
)

WINDOW_MS = int(round(settings.window_seconds * 1000))


# Authentication
# --------------

_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


# Check the shared X-API-Key header.
def require_api_key(key: Optional[str] = Security(_api_key)) -> None:
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    if not key or not secrets.compare_digest(key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# Elasticsearch
# -------------

# Return the Elasticsearch client created by the dashboard.
def get_client():
    # Imported here to avoid a circular import with app.main.
    from .main import client

    return client


# Epoch time
# ----------

RESOLUTIONS: Dict[str, float] = {
    "125ms": 0.125,
    "1s": 1.0,
    "10s": 10.0,
    "1min": 60.0,
    "15min": 900.0,
}


# Convert a resolution name to seconds.
def resolution_seconds(name: str) -> float:
    if name not in RESOLUTIONS:
        raise ValueError(f"resolution must be one of: {', '.join(RESOLUTIONS)}")
    return RESOLUTIONS[name]


# Convert a resolution name to milliseconds.
def resolution_milliseconds(name: str) -> int:
    return int(resolution_seconds(name) * 1000)


# Return the maximum range for a resolution.
def max_span_seconds(resolution: str) -> int:
    return 86400 if resolution == "125ms" else 604800


# Convert an ISO date string to epoch milliseconds in UTC.
def parse_iso_millis(value: str) -> int:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


# Validate the epoch range and its maximum span.
def validate_range(start_ms: int, end_ms: int, resolution: str) -> None:
    if end_ms <= start_ms:
        raise ValueError("'to' must be after 'from'")

    span = (end_ms - start_ms) / 1000.0
    limit = max_span_seconds(resolution)
    if span > limit:
        raise ValueError(
            f"date range too large for resolution {resolution} "
            f"(maximum {limit} seconds)"
        )


# Sensors
# -------

_HWA = re.compile(r"^[0-9a-fA-F]{12}$")


# Read the optional name,hwa CSV mapping.
def load_sensor_names() -> Dict[str, str]:
    path = settings.sensor_names_file
    if not path or not os.path.exists(path):
        return {}

    with open(path, newline="", encoding="utf-8") as stream:
        rows = csv.DictReader(stream)
        return {
            row["name"].strip(): row["hwa"].strip()
            for row in rows
            if row.get("name") and row.get("hwa")
        }


# Return the hwa and display name for a sensor.
def resolve_sensor(name: str) -> Tuple[str, str]:
    names = load_sensor_names()
    if name in names:
        return names[name], name
    if _HWA.match(name):
        return name.lower(), _display_name(name.lower(), names)
    raise HTTPException(status_code=404, detail=f"Unknown sensor: {name}")


# Return the Common Name for an hwa, or the hwa.
def _display_name(hwa: str, names: Dict[str, str]) -> str:
    for name, value in names.items():
        if value == hwa:
            return name
    return hwa


# List sensors from the CSV or the last week of data.
@api_router.get("/sensors")
def list_sensors():
    """List sensors from the CSV, or the hwas active in the last week."""
    names = load_sensor_names()
    if names:
        return [{"name": name, "hwa": hwa} for name, hwa in sorted(names.items())]

    response = get_client().search(
        index=settings.indicators_index,
        body={
            "size": 0,
            "query": {"range": {"date_start": {"gte": "now-7d/d"}}},
            "aggs": {"sensors": {"terms": {"field": "hwa.keyword", "size": 1000}}},
        },
    )
    buckets = response["aggregations"]["sensors"]["buckets"]
    return [{"name": bucket["key"], "hwa": bucket["key"]} for bucket in buckets]


# Indicators
# ----------

PAGE_SIZE = 1000
MAX_RESPONSE_VALUES = 5_000_000
METRICS = ("LAeq", "LZeq", "LCeq")
BANDS = (
    "8HZ", "10HZ", "12.5HZ", "16HZ", "20HZ", "25HZ", "31.5HZ",
    "40HZ", "50HZ", "63HZ", "80HZ", "100HZ", "125HZ", "160HZ",
    "200HZ", "250HZ", "315HZ", "400HZ", "500HZ", "630HZ", "800HZ",
    "1000HZ", "1250HZ", "1600HZ", "2000HZ", "2500HZ", "3150HZ",
    "4000HZ", "5000HZ", "6300HZ", "8000HZ", "10000HZ", "12500HZ",
)
Point = Tuple[int, Dict[str, Optional[float]]]

_SCRIPT_INIT = "state.sums = new HashMap(); state.counts = new HashMap();"
_SCRIPT_MAP = """
long base = doc['date_start'].value.toInstant().toEpochMilli();
def levels = params._source[params.field];
if (levels != null) {
  for (int index = 0; index < levels.size(); index++) {
    def level = levels[index];
    if (level == null) continue;
    long timestamp = base + (long)index * params.window_ms;
    if (timestamp < params.start || timestamp > params.end) continue;
    long key = timestamp / params.resolution_ms;
    double power = Math.pow(10.0, level / 10.0);
    String bucket = String.valueOf(key);
    state.sums.put(bucket, state.sums.getOrDefault(bucket, 0.0) + power);
    state.counts.put(bucket, state.counts.getOrDefault(bucket, 0) + 1);
  }
}
"""
_SCRIPT_COMBINE = "return [state.sums, state.counts];"
_SCRIPT_REDUCE = """
Map sums = new HashMap();
Map counts = new HashMap();
for (def state : states) {
  for (def entry : state[0].entrySet()) {
    sums.put(entry.getKey(), sums.getOrDefault(entry.getKey(), 0.0) + entry.getValue());
  }
  for (def entry : state[1].entrySet()) {
    counts.put(entry.getKey(), counts.getOrDefault(entry.getKey(), 0) + entry.getValue());
  }
}
Map result = new HashMap();
for (def key : sums.keySet()) {
  result.put(key, 10.0 * Math.log10(sums.get(key) / counts.get(key)));
}
return result;
"""


# Build the Elasticsearch filter for an epoch range.
def _overlap_query(hwa: str, start_ms: int, end_ms: int) -> Dict:
    return {
        "bool": {
            "filter": [
                {"term": {"hwa.keyword": hwa}},
                {"range": {"date_start": {"lte": end_ms}}},
                {"range": {"date_end": {"gte": start_ms}}},
            ]
        }
    }


# Extract metric and band arrays from one document.
def _source_series(
    source: Dict,
    include_bands: bool,
    metrics: Optional[List[str]] = None,
) -> Dict[str, List]:
    names = METRICS if metrics is None else metrics
    series = {
        name: source[name]
        for name in names
        if isinstance(source.get(name), list)
    }

    if not include_bands:
        return series

    for name, value in source.items():
        if name in METRICS:
            continue
        if name.endswith("HZ") and isinstance(value, list):
            series[name] = value
        # Older mappings store "12.5HZ" as {"12": {"5HZ": [...]}}.
        elif isinstance(value, dict) and isinstance(value.get("5HZ"), list):
            series[f"{name}.5HZ"] = value["5HZ"]

    return series


# Iterate indicator documents in the epoch range.
def _documents(hwa: str, start_ms: int, end_ms: int) -> Iterator[Dict]:
    body = {
        "query": _overlap_query(hwa, start_ms, end_ms),
        "sort": [{"date_start": "asc"}],
        "size": PAGE_SIZE,
    }

    client = get_client()
    while True:
        response = client.search(index=settings.indicators_index, body=body)
        hits = response["hits"]["hits"]
        if not hits:
            return

        for hit in hits:
            yield hit["_source"]

        if len(hits) < PAGE_SIZE:
            return
        body["search_after"] = hits[-1]["sort"]


# Expand stored arrays into epoch-millisecond points.
def _points(
    documents: Iterable[Dict],
    start_ms: int,
    end_ms: int,
    include_bands: bool,
    metrics: Optional[List[str]] = None,
) -> Iterator[Point]:
    for source in documents:
        date_start = source.get("date_start")
        if isinstance(date_start, list):
            date_start = date_start[0] if date_start else None
        if not date_start:
            continue

        doc_start = parse_iso_millis(date_start)
        series = _source_series(source, include_bands, metrics)
        length = max((len(values) for values in series.values()), default=0)

        for index in range(length):
            timestamp = doc_start + index * WINDOW_MS
            if timestamp < start_ms or timestamp > end_ms:
                continue
            yield timestamp, {
                name: values[index] if index < len(values) else None
                for name, values in series.items()
            }


# Collect raw 125 ms points into column arrays.
def _collect_raw(points: Iterable[Point], metrics: Optional[List[str]]):
    times: List[int] = []
    series: Dict[str, List] = {name: [] for name in (metrics or [])}

    for timestamp, point in points:
        times.append(timestamp)
        for values in series.values():
            values.append(None)
        for name, value in point.items():
            if name not in series:
                series[name] = [None] * (len(times) - 1)
                series[name].append(value)
            else:
                series[name][-1] = value

    return times, series


# Build a server-side energy aggregation for one field.
def _scripted_metric(field: str, start_ms: int, end_ms: int, resolution_ms: int):
    return {
        "scripted_metric": {
            "init_script": _SCRIPT_INIT,
            "map_script": _SCRIPT_MAP,
            "combine_script": _SCRIPT_COMBINE,
            "reduce_script": _SCRIPT_REDUCE,
            "params": {
                "field": field,
                "start": start_ms,
                "end": end_ms,
                "window_ms": WINDOW_MS,
                "resolution_ms": resolution_ms,
            },
        }
    }


# Aggregate fields in Elasticsearch and align the buckets.
def _server_series(
    hwa: str,
    start_ms: int,
    end_ms: int,
    resolution_ms: int,
    fields: List[str],
):
    aggs = {
        f"f{index}": _scripted_metric(field, start_ms, end_ms, resolution_ms)
        for index, field in enumerate(fields)
    }
    response = get_client().search(
        index=settings.indicators_index,
        body={"size": 0, "query": _overlap_query(hwa, start_ms, end_ms), "aggs": aggs},
    )

    values = {}
    for index, field in enumerate(fields):
        result = response["aggregations"][f"f{index}"]["value"] or {}
        values[field] = {int(key): float(level) for key, level in result.items()}

    keys = sorted({key for series in values.values() for key in series})
    times = [key * resolution_ms for key in keys]
    series = {
        field: [values[field].get(key) for key in keys]
        for field in fields
    }
    return times, series


# Sort metrics first, then bands by frequency.
def _sort_names(names: Iterable[str]) -> List[str]:
    # Return the sort key for one field name.
    def key(name: str):
        if name in METRICS:
            return (0, METRICS.index(name), name)
        if name.endswith("HZ"):
            try:
                return (1, float(name[:-2]), name)
            except ValueError:
                pass
        return (2, 0, name)

    return sorted(names, key=key)


# Build the columnar JSON response.
def _result(
    hwa: str,
    display_name: str,
    start_ms: int,
    end_ms: int,
    resolution: str,
    metrics: Optional[List[str]],
    bands: bool,
    times: List[int],
    series: Dict[str, List],
):
    if metrics is None:
        metrics = [
            name
            for name in _sort_names(series)
            if name in METRICS and any(value is not None for value in series[name])
        ]

    band_names = [
        name
        for name in _sort_names(series)
        if name not in METRICS and any(value is not None for value in series[name])
    ]

    return {
        "sensor": {"name": display_name, "hwa": hwa},
        "from": start_ms,
        "to": end_ms,
        "resolution_s": resolution_seconds(resolution),
        "unit": "dB",
        "count": len(times),
        "time": times,
        "metrics": {name: series.get(name, []) for name in metrics},
        "bands": {name: series.get(name, []) for name in band_names} if bands else None,
    }


# Return indicator levels for an epoch range.
@api_router.get("/sensors/{name}/indicators")
def get_indicators(
    name: str,
    from_: int = Query(..., alias="from", ge=0),
    to: int = Query(..., ge=0),
    resolution: str = Query("1min"),
    metrics: Optional[str] = Query(
        None, description="Comma-separated metrics; default: all available"
    ),
    bands: bool = Query(False),
):
    """Return indicator levels between two epoch-millisecond dates."""
    try:
        resolution_seconds(resolution)
        validate_range(from_, to, resolution)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    requested = None
    if metrics:
        requested = [item.strip() for item in metrics.split(",") if item.strip()]
        unknown = [item for item in requested if item not in METRICS]
        if not requested or unknown:
            raise HTTPException(
                status_code=400,
                detail=f"metrics must contain only: {', '.join(METRICS)}",
            )

    if resolution == "125ms" and WINDOW_MS != 125:
        raise HTTPException(
            status_code=500,
            detail="INDICATOR_WINDOW_SECONDS must be 0.125 for 125ms resolution",
        )

    # A full day of bands would produce hundreds of MB in one response.
    points = (to - from_) // WINDOW_MS + 1
    series_count = len(requested) if requested else len(METRICS)
    if bands:
        series_count += len(BANDS)
    if points * series_count > MAX_RESPONSE_VALUES:
        raise HTTPException(
            status_code=400,
            detail="response too large; reduce the range, use a coarser "
            "resolution, or set bands=false",
        )

    hwa, display_name = resolve_sensor(name)

    if resolution == "125ms":
        points = _points(_documents(hwa, from_, to), from_, to, bands, requested)
        times, series = _collect_raw(points, requested)
    else:
        fields = list(requested) if requested else list(METRICS)
        if bands:
            fields += list(BANDS)
        times, series = _server_series(
            hwa,
            from_,
            to,
            resolution_milliseconds(resolution),
            fields,
        )

    return _result(
        hwa,
        display_name,
        from_,
        to,
        resolution,
        requested,
        bands,
        times,
        series,
    )


# Recognition events
# ------------------

MAX_EVENT_SPAN_SECONDS = 604800


# Read an event time as epoch milliseconds.
def _event_time(source: Dict) -> Optional[int]:
    value = source.get("date")
    if isinstance(value, str):
        return parse_iso_millis(value)
    if isinstance(value, (int, float)):
        return int(value)

    value = source.get("timestamp")
    if isinstance(value, (int, float)):
        return int(value)
    return None


# Return triggered events for an epoch range.
@api_router.get("/sensors/{name}/events")
def get_events(
    name: str,
    from_: int = Query(..., alias="from", ge=0),
    to: int = Query(..., ge=0),
    tags: Optional[str] = Query(
        None, description="Yamnet tags; use | between tags"
    ),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(1000, ge=1, le=5000),
):
    """Return triggered recognition events between two epoch-millisecond dates."""
    if to <= from_:
        raise HTTPException(status_code=400, detail="'to' must be after 'from'")
    if (to - from_) / 1000.0 > MAX_EVENT_SPAN_SECONDS:
        raise HTTPException(
            status_code=400, detail="date range too large (maximum one week)"
        )

    tag_text = tags.strip() if tags else ""
    separator = "|" if "|" in tag_text else ","
    wanted = [item.strip() for item in tag_text.split(separator) if item.strip()]
    hwa, display_name = resolve_sensor(name)

    query = {
        "bool": {
            "filter": [
                {"term": {"hwa.keyword": hwa}},
                {
                    "range": {
                        "date": {
                            "gte": from_,
                            "lte": to,
                            "format": "epoch_millis",
                        }
                    }
                },
            ]
        }
    }

    events: List[Dict] = []
    response = get_client().search(
        index=settings.events_index,
        query=query,
        size=5000,
        sort=[{"date": "asc"}],
    )
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        timestamp = _event_time(source)
        if timestamp is None:
            continue

        scores = source.get("scores") or {}
        orders = source.get("orders") or {}
        if not isinstance(scores, dict):
            scores = {}
        if not isinstance(orders, dict):
            orders = {}

        if tag_text:
            # A tag can contain a comma; use "|" to combine several tags.
            if tag_text in scores:
                relevant = [scores[tag_text]]
            else:
                relevant = [
                    scores[tag]
                    for tag in wanted
                    if isinstance(scores.get(tag), (int, float))
                ]
            if not relevant:
                continue
        else:
            relevant = [
                value
                for value in scores.values()
                if isinstance(value, (int, float))
            ]

        if min_score > 0 and (not relevant or max(relevant) < min_score):
            continue

        events.append(
            {
                "id": hit["_id"],
                "time": timestamp,
                "leq": source.get("leq"),
                "scores": scores,
                "orders": orders,
            }
        )

    events.sort(key=lambda item: item["time"])
    events = events[:limit]

    return {
        "sensor": {"name": display_name, "hwa": hwa},
        "from": from_,
        "to": to,
        "count": len(events),
        "events": events,
    }
