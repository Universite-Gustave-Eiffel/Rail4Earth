"""Sound level and recognition API mounted under /api/v1."""

from __future__ import annotations

import csv
import math
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo

from elasticsearch.helpers import scan
from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

api_router = APIRouter()


# Settings
# --------

@dataclass(frozen=True)
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


# Authentication
# --------------

_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: Optional[str] = Security(_api_key)) -> None:
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    if not key or not secrets.compare_digest(key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# Elasticsearch
# -------------

def get_client():
    # Imported here to avoid a circular import with app.main.
    from .main import client

    return client


# Time
# ----

PARIS = ZoneInfo("Europe/Paris")
UTC = timezone.utc

RESOLUTIONS: Dict[str, float] = {
    "125ms": 0.125,
    "1s": 1.0,
    "10s": 10.0,
    "1min": 60.0,
    "15min": 900.0,
}


def resolution_seconds(name: str) -> float:
    if name not in RESOLUTIONS:
        raise ValueError(f"resolution must be one of: {', '.join(RESOLUTIONS)}")
    return RESOLUTIONS[name]


def max_span_seconds(resolution: str) -> int:
    return 86400 if resolution == "125ms" else 604800


def parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PARIS)
    return parsed.astimezone(UTC)


def to_paris_iso(value: datetime) -> str:
    return value.astimezone(PARIS).isoformat(timespec="milliseconds")


def validate_range(start: datetime, end: datetime, resolution: str) -> None:
    if end <= start:
        raise ValueError("'to' must be after 'from'")

    span = (end - start).total_seconds()
    limit = max_span_seconds(resolution)
    if span > limit:
        raise ValueError(
            f"date range too large for resolution {resolution} "
            f"(maximum {limit} seconds)"
        )


def aligned_bucket(value: datetime, seconds: float) -> int:
    return int(value.timestamp() // seconds)


def bucket_time(bucket: int, seconds: float) -> datetime:
    return datetime.fromtimestamp(bucket * seconds, tz=UTC)


# Sensors
# -------

_HWA = re.compile(r"^[0-9a-fA-F]{12}$")


def load_sensor_names() -> Dict[str, str]:
    """Read an optional CSV with columns: name,hwa."""
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


def resolve_sensor(name: str) -> Tuple[str, str]:
    """Return (hwa, display_name) for a Common Name or a raw hwa."""
    names = load_sensor_names()
    if name in names:
        return names[name], name
    if _HWA.match(name):
        return name.lower(), _display_name(name.lower(), names)
    raise HTTPException(status_code=404, detail=f"Unknown sensor: {name}")


def _display_name(hwa: str, names: Dict[str, str]) -> str:
    for name, value in names.items():
        if value == hwa:
            return name
    return hwa


@api_router.get("/sensors")
def list_sensors():
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
Point = Tuple[datetime, Dict[str, Optional[float]]]


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


def _documents(hwa: str, start: datetime, end: datetime) -> Iterator[Dict]:
    body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"hwa.keyword": hwa}},
                    {"range": {"date_start": {"lte": end.isoformat()}}},
                    {"range": {"date_end": {"gte": start.isoformat()}}},
                ]
            }
        },
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


def _points(
    documents: Iterable[Dict],
    start: datetime,
    end: datetime,
    include_bands: bool,
    metrics: Optional[List[str]] = None,
) -> Iterator[Point]:
    window = settings.window_seconds

    for source in documents:
        date_start = source.get("date_start")
        if not date_start:
            continue

        doc_start = parse_datetime(date_start)
        series = _source_series(source, include_bands, metrics)
        length = max((len(values) for values in series.values()), default=0)

        for index in range(length):
            timestamp = doc_start + timedelta(seconds=index * window)
            if timestamp < start or timestamp > end:
                continue
            yield timestamp, {
                name: values[index] if index < len(values) else None
                for name, values in series.items()
            }


def _collect_raw(points: Iterable[Point], metrics: Optional[List[str]]):
    times: List[datetime] = []
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


def _collect_buckets(
    points: Iterable[Point],
    resolution: float,
    metrics: Optional[List[str]],
):
    buckets: Dict[int, Dict] = {}

    for timestamp, point in points:
        key = aligned_bucket(timestamp, resolution)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {"time": bucket_time(key, resolution), "sums": {}, "counts": {}}
            buckets[key] = bucket

        for name, value in point.items():
            if value is None:
                continue
            try:
                level = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(level):
                continue
            bucket["sums"][name] = bucket["sums"].get(name, 0.0) + 10 ** (level / 10)
            bucket["counts"][name] = bucket["counts"].get(name, 0) + 1

    names = set(metrics or [])
    for bucket in buckets.values():
        names.update(bucket["counts"])

    times = []
    series: Dict[str, List] = {name: [] for name in names}
    for key in sorted(buckets):
        bucket = buckets[key]
        times.append(bucket["time"])
        for name, values in series.items():
            count = bucket["counts"].get(name, 0)
            if count:
                values.append(
                    round(10 * math.log10(bucket["sums"][name] / count), 2)
                )
            else:
                values.append(None)

    return times, series


def _sort_names(names: Iterable[str]) -> List[str]:
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


def _result(
    hwa: str,
    display_name: str,
    start: datetime,
    end: datetime,
    resolution: str,
    metrics: Optional[List[str]],
    bands: bool,
    times: List[datetime],
    series: Dict[str, List],
):
    band_names = [name for name in _sort_names(series) if name not in METRICS]
    if metrics is None:
        metrics = [name for name in _sort_names(series) if name in METRICS]

    return {
        "sensor": {"name": display_name, "hwa": hwa},
        "from": to_paris_iso(start),
        "to": to_paris_iso(end),
        "resolution_s": resolution_seconds(resolution),
        "unit": "dB",
        "count": len(times),
        "time": [to_paris_iso(value) for value in times],
        "metrics": {name: series.get(name, []) for name in metrics},
        "bands": {name: series.get(name, []) for name in band_names} if bands else None,
    }


@api_router.get("/sensors/{name}/indicators")
def get_indicators(
    name: str,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    resolution: str = Query("1min"),
    metrics: Optional[str] = Query(
        None, description="Comma-separated metrics; default: all available"
    ),
    bands: bool = Query(False),
):
    try:
        resolution_value = resolution_seconds(resolution)
        start = parse_datetime(from_)
        end = parse_datetime(to)
        validate_range(start, end, resolution)
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

    if resolution == "125ms" and abs(settings.window_seconds - 0.125) > 1e-9:
        raise HTTPException(
            status_code=500,
            detail="INDICATOR_WINDOW_SECONDS must be 0.125 for 125ms resolution",
        )

    # A full day of bands would produce hundreds of MB in one response.
    points = int((end - start).total_seconds() / settings.window_seconds) + 1
    series_count = len(requested) if requested else len(METRICS)
    if bands:
        series_count += 33
    if points * series_count > MAX_RESPONSE_VALUES:
        raise HTTPException(
            status_code=400,
            detail="response too large; reduce the range, use a coarser "
            "resolution, or set bands=false",
        )

    hwa, display_name = resolve_sensor(name)
    points = _points(_documents(hwa, start, end), start, end, bands, requested)

    if resolution == "125ms":
        times, series = _collect_raw(points, requested)
    else:
        times, series = _collect_buckets(points, resolution_value, requested)

    return _result(
        hwa,
        display_name,
        start,
        end,
        resolution,
        requested,
        bands,
        times,
        series,
    )


# Recognition events
# ------------------

MAX_EVENT_SPAN_SECONDS = 604800


def _event_time(source: Dict) -> Optional[datetime]:
    value = source.get("date")
    if isinstance(value, str):
        return parse_datetime(value)

    value = source.get("timestamp")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=UTC)
    return None


@api_router.get("/sensors/{name}/events")
def get_events(
    name: str,
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    tags: Optional[str] = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(1000, ge=1, le=5000),
):
    try:
        start = parse_datetime(from_)
        end = parse_datetime(to)
        if end <= start:
            raise ValueError("'to' must be after 'from'")
        if (end - start).total_seconds() > MAX_EVENT_SPAN_SECONDS:
            raise ValueError("date range too large (maximum one week)")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    wanted = [item.strip() for item in tags.split(",") if item.strip()] if tags else []
    hwa, display_name = resolve_sensor(name)

    query = {
        "bool": {
            "filter": [
                {"term": {"hwa.keyword": hwa}},
                {"range": {"date": {"gte": start.isoformat(), "lte": end.isoformat()}}},
            ]
        }
    }

    events: List[Dict] = []
    for hit in scan(
        get_client(),
        index=settings.events_index,
        query=query,
        size=1000,
    ):
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

        if wanted:
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

    for event in events:
        event["time"] = to_paris_iso(event["time"])

    return {
        "sensor": {"name": display_name, "hwa": hwa},
        "from": to_paris_iso(start),
        "to": to_paris_iso(end),
        "count": len(events),
        "events": events,
    }
