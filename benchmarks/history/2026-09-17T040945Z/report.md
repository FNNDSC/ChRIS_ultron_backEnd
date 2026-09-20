# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T040945Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 5  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 19.43 | 122.7 | 0 | 5 |  |
| 10 | PASS | 20.48 | 75.4 | 0 | 5 |  |
| 100 | PASS | 20.38 | 88.9 | 0 | 5 |  |
| 1000 | PASS | 38.78 | 76.9 | 0 | 5 |  |
| 10000 | PASS | 189.17 | 55.9 | 0 | 5 |  |

_Peak CPU at level 10000: worker-mains 100.9% (per service: {'worker-mains': 100.9, 'celery-scheduler': 3.3, 'chris': 9.1, 'worker-periodic': 18.4, 'dragonflydb': 14.8, 'db': 42.7, 'pfcon': 0.0, 'nats': 0.1})_

_Peak disk write at level 10000: db 69.9 MiB (per service: {'worker-mains': '10.7 MiB', 'worker-periodic': '104.0 KiB', 'db': '69.9 MiB', 'pfcon': '32.0 KiB'})_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-31-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132318998528 |
| Docker root | /var/lib/docker |
| Engine | 29.8.0 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 12.4 / 13.4 |

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

### Workload plugins

| Role | Plugin | Version | Installed versions |
|---|---|---|---|
| fs | dbg-bigfiles | 1.0.0 | 1 |
| ds | pl-simpledsapp | 2.1.5 | 1 |
| ts | pl-topologicalcopy | 1.0.13 | 1 |

### Manual fields (fill in)

- **storage_device_type_throughput:** TODO
- **power_thermal_mode:** TODO
- **other_significant_workloads:** TODO

