# CUBE Control-Plane RED — Locust Report

_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). Pair with the data-plane per-run `report.md` files for the full picture._

## Read-only saturation sweep

| Users | Requests | Failures | Fail % | RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|
| 25 | 5404 | 0 | 0.0% | 61 | 29 | 75 | 270 |
| 50 | 8624 | 303 | 3.5% | 97 | 51 | 160 | 1200 |
| 100 | 935 | 678 | 72.5% | 10 | 10000 | 24000 | 69000 |
| 200 | 2415 | 1601 | 66.3% | 27 | 710 | 16000 | 61000 |
| 400 | 3129 | 2115 | 67.6% | 35 | 2100 | 24000 | 25000 |

## Top failures (read_u400_failures.csv)

| Occurrences | Endpoint | Error |
|---|---|---|
| 788 | list-instances | CatchResponseError('HTTP 500') |
| 683 | list-files | CatchResponseError('HTTP 401') |
| 400 | auth-token | CatchResponseError('auth HTTP 500') |
| 244 | search-plugins | CatchResponseError('HTTP 500') |

