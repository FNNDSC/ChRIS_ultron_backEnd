# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T192652Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 5  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| diamond | layers | 16 | scenario_timeout |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.81 | 201.2 | 0 | 6 |  |
| 2 | PASS | 19.86 | 190.8 | 0 | 11 |  |
| 4 | PASS | 41.05 | 116.9 | 0 | 21 |  |
| 8 | PASS | 3363.53 | 1126.5 | 0 | 41 |  |
| 16 | FAIL | 3420.56 | 1412.3 | 0 | 41 | scenario_timeout |

_Peak CPU at level 16: worker-mains 405.2% (per service: {'celery-scheduler': 4.4, 'chris': 80.4, 'worker-periodic': 21.6, 'worker-mains': 405.2, 'pfcon': 4.8, 'dragonflydb': 11.5, 'db': 212.7, 'nats': 0.2})_

_Peak disk write at level 16: db 40.9 GiB (per service: {'worker-periodic': '3.0 MiB', 'worker-mains': '2.8 GiB', 'pfcon': '300.0 KiB', 'db': '40.9 GiB'})_

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
| Noise floor (health p50/p95 ms) | 6.2 / 7.5 |

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

