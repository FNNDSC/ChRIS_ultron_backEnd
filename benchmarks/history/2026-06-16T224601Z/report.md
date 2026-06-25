# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T224601Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 5  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 7.28 | 184.9 | 0 | 2 |  |
| 2 | PASS | 11.6 | 60.4 | 0 | 3 |  |
| 4 | PASS | 20.22 | 101.5 | 0 | 5 |  |
| 8 | PASS | 36.12 | 175.3 | 0 | 9 |  |
| 16 | PASS | 67.25 | 97.0 | 0 | 17 |  |

_Peak CPU at level 16: worker-mains 41.7% (per service: {'celery-scheduler': 3.8, 'worker-mains': 41.7, 'chris': 18.5, 'worker-periodic': 14.4, 'pfcon': 3.5, 'db': 22.4, 'dragonflydb': 6.1, 'nats': 0.0})_

_Peak disk write at level 16: db 2.1 MiB (per service: {'worker-mains': '664.0 KiB', 'worker-periodic': '156.0 KiB', 'pfcon': '104.0 KiB', 'db': '2.1 MiB'})_

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
| Noise floor (health p50/p95 ms) | 11.4 / 12.5 |

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

