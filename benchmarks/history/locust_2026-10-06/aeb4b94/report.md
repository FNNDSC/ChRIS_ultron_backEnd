# CUBE Control-Plane RED — Locust Report

_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). Pair with the data-plane per-run `report.md` files for the full picture._

## Read-only saturation sweep

| Users | Requests | Failures | Fail % | RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|
| 100 | 22252 | 1531 | 6.9% | 250 | 9 | 26 | 190 |
| 400 | 3864 | 2721 | 70.4% | 43 | 10000 | 29000 | 62000 |

## Top failures (read_u400_failures.csv)

| Occurrences | Endpoint | Error |
|---|---|---|
| 990 | list-instances | CatchResponseError('HTTP 500') |
| 678 | list-files | CatchResponseError('HTTP 401') |
| 458 | search-plugins | CatchResponseError('HTTP 500') |
| 288 | auth-token | CatchResponseError('auth HTTP 500') |
| 182 | list-feeds | CatchResponseError('HTTP 500') |
| 125 | list-files | CatchResponseError('HTTP 500') |

