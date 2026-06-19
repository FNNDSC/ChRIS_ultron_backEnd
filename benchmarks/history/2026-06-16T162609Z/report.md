# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T162609Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 6  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | feeds | 32 | cancelled:inst-5106; cancelled:inst-5105 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 74.17 | 872.3 | 0 | 6 |  |
| 2 | PASS | 75.08 | 589.4 | 0 | 12 |  |
| 4 | PASS | 74.62 | 104.2 | 0 | 24 |  |
| 8 | PASS | 81.47 | 403.9 | 0 | 48 |  |
| 16 | PASS | 113.15 | 547.7 | 0 | 96 |  |
| 32 | FAIL | 138.87 | 494.5 | 0 | 190 | cancelled:inst-5106; cancelled:inst-5105 |

_Peak CPU at level 32: db 194.8% (per service: {'worker-periodic': 23.0, 'worker-mains': 184.5, 'chris': 63.9, 'celery-scheduler': 2.9, 'pfcon': 11.0, 'db': 194.8, 'nats': 0.1, 'dragonflydb': 11.6})_

_Peak disk write at level 32: db 49.7 MiB (per service: {'worker-periodic': '532.0 KiB', 'worker-mains': '10.2 MiB', 'pfcon': '1.3 MiB', 'db': '49.7 MiB'})_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-22-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132319051776 |
| Docker root | /var/lib/docker |
| Engine | 27.3.0 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 12.0 / 13.9 |

### Envelope (recorded knobs)

| Knob | Value |
|---|---|
| CUBE_CELERY_POLL_INTERVAL | 2.0 |
| CUBE_UVICORN_WORKERS | 4 |
| CUBE_DB_POOL_MIN_SIZE | 2 |
| CUBE_DB_POOL_MAX_SIZE | 10 |
| CUBE_DB_POOL_TIMEOUT | 10 |
| CUBE_DB_MAX_CONNECTIONS | 300 |
| CUBE_WORKER_MAINS_CONCURRENCY | 4 |
| PFCON_WORKERS | 8 |
| STORAGE_ENV | fslink |

### Manual fields (fill in)

- **storage_device_type_throughput:** TODO
- **power_thermal_mode:** TODO
- **other_significant_workloads:** TODO

