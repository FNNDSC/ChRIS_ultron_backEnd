# CUBE Control-Plane RED — Locust Report

_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). Pair with the data-plane per-run `report.md` files for the full picture._

## Read-only saturation sweep

| Users | Requests | Failures | Fail % | RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|
| 25 | 5970 | 0 | 0.0% | 67 | 22 | 61 | 190 |
| 50 | 10415 | 226 | 2.2% | 117 | 32 | 110 | 520 |
| 100 | 4339 | 895 | 20.6% | 49 | 39 | 10000 | 17000 |
| 200 | 7247 | 1225 | 16.9% | 81 | 580 | 11000 | 14000 |
| 400 | 3653 | 2427 | 66.4% | 41 | 8000 | 22000 | 61000 |

## Write-path run (u=10, healthy stack)

| Endpoint | Requests | Failures | p50 (ms) | p95 (ms) |
|---|---|---|---|---|
| auth-token | 10 | 0 | 700 | 1700 |
| create-instance | 97 | 0 | 62 | 140 |
| list-feeds | 501 | 0 | 51 | 110 |
| list-files | 353 | 0 | 26 | 69 |
| list-instances | 499 | 0 | 72 | 150 |
| search-plugins | 188 | 0 | 18 | 50 |
| Aggregated | 1648 | 0 | 52 | 120 |

## Top failures (read_u400_failures.csv)

| Occurrences | Endpoint | Error |
|---|---|---|
| 919 | list-instances | CatchResponseError('HTTP 500') |
| 669 | list-files | CatchResponseError('HTTP 401') |
| 315 | search-plugins | CatchResponseError('HTTP 500') |
| 312 | auth-token | CatchResponseError('auth HTTP 500') |
| 146 | list-feeds | CatchResponseError('HTTP 500') |
| 66 | list-files | CatchResponseError('HTTP 500') |

