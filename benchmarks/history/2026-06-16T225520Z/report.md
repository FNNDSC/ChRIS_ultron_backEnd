# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T225520Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 5  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 26.12 | 211.2 | 0 | 2 |  |
| 2 | PASS | 47.28 | 77.1 | 0 | 3 |  |
| 4 | PASS | 75.07 | 159.6 | 0 | 5 |  |
| 8 | PASS | 142.46 | 77.5 | 0 | 9 |  |
| 16 | PASS | 269.31 | 115.8 | 0 | 17 |  |

_Peak CPU at level 16: worker-mains 24.4% (per service: {'celery-scheduler': 3.2, 'chris': 18.5, 'worker-mains': 24.4, 'worker-periodic': 14.1, 'pfcon': 2.9, 'db': 15.8, 'dragonflydb': 5.7, 'nats': 0.1})_

_Peak disk write at level 16: db 4.1 MiB (per service: {'worker-mains': '868.0 KiB', 'worker-periodic': '232.0 KiB', 'pfcon': '128.0 KiB', 'db': '4.1 MiB'})_

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
| Noise floor (health p50/p95 ms) | 10.9 / 15.2 |

### Envelope (recorded knobs)

| Knob | Value |
|---|---|
| CUBE_CELERY_POLL_INTERVAL | 8 |
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

