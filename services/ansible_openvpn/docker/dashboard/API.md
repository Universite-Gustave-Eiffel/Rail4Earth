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
    ?from=1792659600000
    &to=1792663200000
    &resolution=1min
    &metrics=LZeq
    &bands=false
```

| Parameter | Values | Default |
|---|---|---|
| `from`, `to` | epoch milliseconds (UTC) | required |
| `resolution` | `125ms`, `1s`, `10s`, `1min`, `15min` | `1min` |
| `metrics` | `LAeq`, `LZeq`, `LCeq` (comma-separated) | all available |
| `bands` | `true` / `false` | `false` |

`name` is either a Common Name from the CSV or a raw `hwa`.

Limits: `125ms` to 1 day; other resolutions to 1 week. A `bands=true` request
that would exceed 5 million values is rejected.

```bash
curl --compressed -H "X-API-Key: $R4E_API_KEY" \
  "https://<dashboard-host>/api/v1/sensors/b827eb9af680/indicators?\
from=1792659600000&to=1792663200000&resolution=1min&metrics=LZeq"
```

Response:

```json
{
  "sensor": {"name": "b827eb9af680", "hwa": "b827eb9af680"},
  "from": 1792659600000,
  "to": 1792663200000,
  "resolution_s": 60.0,
  "unit": "dB",
  "count": 1,
  "time": [1792661697000],
  "metrics": {"LZeq": [56.8]},
  "bands": null
}
```

All times are epoch milliseconds in UTC. Arrays are columnar and have the
same length. Aggregated values are computed in Elasticsearch as energy
averages (`10*log10(mean(10**(L/10)))`).

## Recognition events

```http
GET /api/v1/sensors/{name}/events
    ?from=1733875200000
    &to=1733961600000
    &tags=Train%7CRail%20transport
    &min_score=0.1
    &limit=100
```

| Parameter | Meaning | Default |
|---|---|---|
| `from`, `to` | maximum one week | required |
| `tags` | Yamnet tags; separate multiple tags with `|` | all |
| `min_score` | minimum relevant score | `0` |
| `limit` | maximum returned events (1-5000) | `1000` |

A tag can contain a comma, for example `Railroad car, train wagon`. Pass it
alone, or combine it with `|`, for example
`tags=Train%7CRailroad%20car%2C%20train%20wagon`.

Response:

```json
{
  "sensor": {"name": "b827eb9af680", "hwa": "b827eb9af680"},
  "count": 1,
  "events": [{
    "id": "...",
    "time": 1733915317511,
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
