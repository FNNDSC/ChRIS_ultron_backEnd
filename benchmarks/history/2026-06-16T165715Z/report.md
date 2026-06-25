# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T165715Z  •  **Tier:** aging-probe  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 1  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 9.36 | 440.6 | 0 | 6 |  |

_Peak CPU at level 1: pfcon 35.7% (per service: {'worker-periodic': 15.8, 'worker-mains': 8.6, 'chris': 4.3, 'celery-scheduler': 2.5, 'pfcon': 35.7, 'db': 15.3, 'nats': 0.0, 'dragonflydb': 5.5})_

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
| Noise floor (health p50/p95 ms) | 11.8 / 13.3 |

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

