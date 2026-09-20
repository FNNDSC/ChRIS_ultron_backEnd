# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T054841Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 5  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 13.68 | 119.4 | 0 | 2 |  |
| 2 | PASS | 24.42 | 60.1 | 0 | 3 |  |
| 4 | PASS | 37.87 | 177.8 | 0 | 5 |  |
| 8 | PASS | 69.87 | 91.7 | 0 | 9 |  |
| 16 | PASS | 132.28 | 102.4 | 0 | 17 |  |

_Peak CPU at level 16: db 25.7% (per service: {'celery-scheduler': 2.5, 'chris': 16.0, 'worker-periodic': 19.2, 'worker-mains': 25.1, 'nats': 0.1, 'dragonflydb': 18.0, 'pfcon': 3.1, 'db': 25.7})_

_Peak disk write at level 16: db 2.8 MiB (per service: {'worker-periodic': '180.0 KiB', 'worker-mains': '784.0 KiB', 'pfcon': '120.0 KiB', 'db': '2.8 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.1 / 14.7 |

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

