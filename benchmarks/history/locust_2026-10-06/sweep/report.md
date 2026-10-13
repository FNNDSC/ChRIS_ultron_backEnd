# CUBE Control-Plane RED — Locust Report

_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). Pair with the data-plane per-run `report.md` files for the full picture._

## Read-only saturation sweep

| Users | Requests | Failures | Fail % | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Healthy before | Recovered |
|---|---|---|---|---|---|---|---|---|---|
| 25 | 6402 | 0 | 0.0% | 71 | 12 | 23 | 140 | yes | yes, 0 s |
| 50 | 11874 | 41 | 0.3% | 132 | 10 | 26 | 470 | yes | yes, 0 s |
| 100 | 22057 | 1744 | 7.9% | 246 | 10 | 35 | 1100 | yes | yes, 0 s |
| 200 | 37342 | 5147 | 13.8% | 416 | 34 | 190 | 3000 | yes | yes, 0 s |
| 400 | 39053 | 7179 | 18.4% | 435 | 320 | 710 | 12000 | yes | yes, 0 s |

_Healthy before: the API answered a burst of probes before the step started. Recovered: seconds after the step until it did again, with every API worker's pool back to no checked-out connections. A step that started on an unhealthy stack measured a broken stack._

## Top failures (read_u400_failures.csv)

| Occurrences | Endpoint | Error |
|---|---|---|
| 6829 | list-files | CatchResponseError('HTTP 401') |
| 311 | auth-token | CatchResponseError('auth HTTP 500') |
| 22 | search-plugins | CatchResponseError('HTTP 500') |
| 17 | list-instances | CatchResponseError('HTTP 500') |

