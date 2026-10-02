# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T072731Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.82 | 148.8 | 0 | 6 |  |
| 2 | PASS | 19.87 | 81.5 | 0 | 11 |  |
| 4 | PASS | 41.49 | 92.1 | 0 | 21 |  |
| 8 | PASS | 3259.57 | 1129.6 | 0 | 41 |  |

_Peak CPU at level 8: worker-mains 402.5% (per service: {'chris': 77.1, 'worker-mains': 402.5, 'worker-periodic': 28.9, 'celery-scheduler': 4.8, 'nats': 0.3, 'db': 208.5, 'pfcon': 50.7, 'dragonflydb': 15.5})_

_Peak disk write at level 8: db 30.5 GiB (per service: {'worker-mains': '2.1 GiB', 'worker-periodic': '768.0 KiB', 'db': '30.5 GiB', 'pfcon': '276.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.0 / 14.8 |

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

