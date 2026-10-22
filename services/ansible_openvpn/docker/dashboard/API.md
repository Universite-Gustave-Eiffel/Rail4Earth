# Dashboard API v1

JSON endpoints for sensor levels and triggered recognition events.
Base URL: `https://<dashboard-host>/api/v1`.

All routes require the shared key configured in `R4E_API_KEY`:

```bash
-H "X-API-Key: $R4E_API_KEY"
```

## Sensors

```http
GET /api/v1/sensors
```

Returns the sensors available in the optional `SENSOR_NAMES_FILE` CSV
(`name,hwa`), or the `hwa` values that produced data in the last seven days.

```json
[{"name": "Sensor 01", "hwa": "b827eb9af680"}]
```

## Indicators

```http
GET /api/v1/sensors/{name}/indicators
    ?from=2026-10-22T11:00:00
    &to=2026-10-22T11:01:00
    &resolution=1min
    &metrics=LZeq
    &bands=false
```

| Parameter | Values | Default |
|---|---|---|
| `from`, `to` | ISO 8601; Europe/Paris if no offset | required |
| `resolution` | `125ms`, `1s`, `10s`, `1min`, `15min` | `1min` |
| `metrics` | `LAeq`, `LZeq`, `LCeq` (comma-separated) | all available |
| `bands` | `true` / `false` | `false` |

`name` is either a Common Name from the CSV or a raw `hwa`.

Limits: `125ms` to 1 day; other resolutions to 1 week. A `bands=true` request
that would exceed 5 million values is rejected.

```bash
curl --compressed -H "X-API-Key: $R4E_API_KEY" \
  "https://<dashboard-host>/api/v1/sensors/b827eb9af680/indicators?\
from=2026-10-22T11:00:00&to=2026-10-22T11:01:00&resolution=1min&metrics=LZeq"
```

Response:

```json
{
  "sensor": {"name": "b827eb9af680", "hwa": "b827eb9af680"},
  "from": "2026-10-22T11:00:00.000+02:00",
  "to": "2026-10-22T11:01:00.000+02:00",
  "resolution_s": 60.0,
  "unit": "dB",
  "count": 1,
  "time": ["2026-10-22T11:00:00.000+02:00"],
  "metrics": {"LZeq": [56.8]},
  "bands": null
}
```

Arrays are columnar and have the same length. Aggregated values are energy
averages (`10*log10(mean(10**(L/10)))`), aligned on the resolution in UTC.

## Recognition events

```http
GET /api/v1/sensors/{name}/events
    ?from=2026-12-11T00:00:00
    &to=2026-12-12T00:00:00
    &tags=Train
    &min_score=0.1
    &limit=100
```

| Parameter | Meaning | Default |
|---|---|---|
| `from`, `to` | maximum one week | required |
| `tags` | comma-separated Yamnet tags | all |
| `min_score` | minimum relevant score | `0` |
| `limit` | maximum returned events (1-5000) | `1000` |

Response:

```json
{
  "sensor": {"name": "b827eb9af680", "hwa": "b827eb9af680"},
  "count": 1,
  "events": [{
    "id": "...",
    "time": "2024-12-11T12:08:37.511+01:00",
    "leq": 77.06,
    "scores": {"Train": 0.38},
    "orders": {"Train": 3}
  }]
}
```

Only triggered events are returned. Audio and spectrograms are never included.

## Configuration

- `R4E_API_KEY`: shared key for `/api/v1` (required).
- `SENSOR_NAMES_FILE`: optional CSV with columns `name,hwa`.
- `INDICATORS_INDEX`, `EVENTS_INDEX`, `INDICATOR_WINDOW_SECONDS`: optional
  overrides.

The API uses the Elasticsearch client already configured by the dashboard in
`certs/api.json`.
