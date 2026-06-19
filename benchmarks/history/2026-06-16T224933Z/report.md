# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T224933Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 5  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 13.59 | 111.3 | 0 | 2 |  |
| 2 | PASS | 24.18 | 179.3 | 0 | 3 |  |
| 4 | PASS | 37.41 | 85.8 | 0 | 5 |  |
| 8 | PASS | 69.51 | 85.3 | 0 | 9 |  |
| 16 | PASS | 133.68 | 117.9 | 0 | 17 |  |

_Peak CPU at level 16: db 21.9% (per service: {'worker-periodic': 10.5, 'worker-mains': 17.4, 'celery-scheduler': 3.1, 'chris': 20.2, 'pfcon': 3.0, 'db': 21.9, 'dragonflydb': 6.5, 'nats': 0.1})_

_Peak disk write at level 16: db 2.7 MiB (per service: {'worker-periodic': '204.0 KiB', 'worker-mains': '824.0 KiB', 'pfcon': '120.0 KiB', 'db': '2.7 MiB'})_

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
| Noise floor (health p50/p95 ms) | 12.5 / 15.8 |

### Envelope (recorded knobs)

| Knob | Value |
|---|---|
| CUBE_CELERY_POLL_INTERVAL | 4 |
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

