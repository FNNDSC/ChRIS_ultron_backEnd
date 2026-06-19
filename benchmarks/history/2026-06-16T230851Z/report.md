# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T230851Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 9.38 | 223.8 | 0 | 2 |  |
| 2 | PASS | 12.61 | 72.6 | 0 | 3 |  |
| 4 | PASS | 19.26 | 150.1 | 0 | 5 |  |
| 8 | PASS | 35.24 | 122.3 | 0 | 9 |  |

_Peak CPU at level 8: worker-mains 24.0% (per service: {'chris': 12.2, 'celery-scheduler': 3.0, 'worker-periodic': 15.0, 'worker-mains': 24.0, 'pfcon': 2.8, 'db': 11.5, 'dragonflydb': 6.6, 'nats': 0.0})_

_Peak disk write at level 8: db 824.0 KiB (per service: {'worker-periodic': '96.0 KiB', 'worker-mains': '384.0 KiB', 'pfcon': '32.0 KiB', 'db': '824.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 11.0 / 13.6 |

### Envelope (recorded knobs)

| Knob | Value |
|---|---|
| CUBE_CELERY_POLL_INTERVAL | 2 |
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

