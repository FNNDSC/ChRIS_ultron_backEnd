# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-17T001826Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 89.31 | 175.8 | 0 | 2 |  |
| 2 | PASS | 157.94 | 75.6 | 0 | 3 |  |
| 4 | PASS | 298.64 | 66.3 | 0 | 5 |  |
| 8 | PASS | 591.22 | 73.3 | 0 | 9 |  |

_Peak CPU at level 8: db 13.8% (per service: {'worker-mains': 9.9, 'worker-periodic': 9.3, 'chris': 13.3, 'celery-scheduler': 3.0, 'pfcon': 1.1, 'db': 13.8, 'dragonflydb': 6.7, 'nats': 0.1})_

_Peak disk write at level 8: db 5.4 MiB (per service: {'worker-mains': '776.0 KiB', 'worker-periodic': '300.0 KiB', 'pfcon': '64.0 KiB', 'db': '5.4 MiB'})_

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
| Noise floor (health p50/p95 ms) | 11.3 / 12.3 |

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

