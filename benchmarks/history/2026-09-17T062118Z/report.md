# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T062118Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 75.16 | 128.4 | 0 | 2 |  |
| 2 | PASS | 142.24 | 83.7 | 0 | 3 |  |
| 4 | PASS | 280.05 | 71.3 | 0 | 5 |  |
| 8 | PASS | 550.4 | 91.7 | 0 | 9 |  |

_Peak CPU at level 8: db 25.7% (per service: {'chris': 19.2, 'worker-mains': 19.4, 'celery-scheduler': 3.3, 'worker-periodic': 18.5, 'nats': 0.1, 'dragonflydb': 8.8, 'pfcon': 1.3, 'db': 25.7})_

_Peak disk write at level 8: db 3.5 MiB (per service: {'worker-mains': '612.0 KiB', 'worker-periodic': '156.0 KiB', 'pfcon': '56.0 KiB', 'db': '3.5 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.4 / 14.4 |

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

