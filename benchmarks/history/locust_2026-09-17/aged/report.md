# CUBE Control-Plane RED — Locust Report

_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). Pair with the data-plane per-run `report.md` files for the full picture._

## Read-only saturation sweep

| Users | Requests | Failures | Fail % | RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|
| 25 | 568 | 0 | 0.0% | 6 | 1700 | 15000 | 17000 |
| 50 | 792 | 88 | 11.1% | 9 | 2700 | 22000 | 25000 |
| 100 | 881 | 639 | 72.5% | 10 | 10000 | 24000 | 70000 |
| 200 | 2309 | 1562 | 67.6% | 26 | 820 | 16000 | 60000 |
| 400 | 3349 | 2234 | 66.7% | 38 | 1700 | 26000 | 60000 |

## Top failures (read_u400_failures.csv)

| Occurrences | Endpoint | Error |
|---|---|---|
| 866 | list-instances | CatchResponseError('HTTP 500') |
| 718 | list-files | CatchResponseError('HTTP 401') |
| 400 | auth-token | CatchResponseError('auth HTTP 500') |
| 250 | search-plugins | CatchResponseError('HTTP 500') |

