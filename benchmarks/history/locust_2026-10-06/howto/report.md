# CUBE Control-Plane RED — Locust Report

_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). Pair with the data-plane per-run `report.md` files for the full picture._

## Run: `howto_u100`

| Endpoint | Requests | Failures | p50 (ms) | p95 (ms) |
|---|---|---|---|---|
| auth-token | 100 | 34 | 12000 | 18000 |
| list-feeds | 7234 | 0 | 9 | 28 |
| list-files | 4913 | 1686 | 10 | 36 |
| list-instances | 7326 | 0 | 10 | 30 |
| search-plugins | 2547 | 0 | 13 | 98 |
| Aggregated | 22120 | 1720 | 10 | 35 |

Healthy before: yes. Recovered: yes, 0 s.

