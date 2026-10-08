# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-07T005703Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 911fb6c (dirty: true)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.52 | 80.7 | 0 | 6 |  |
| 2 | PASS | 19.24 | 44.3 | 0 | 11 |  |
| 4 | PASS | 41.04 | 46.0 | 0 | 21 |  |
| 8 | PASS | 2906.49 | 814.1 | 0 | 41 |  |

_Peak CPU at level 8: worker-mains 401.8% (per service: {'chris': 70.8, 'worker-mains': 401.8, 'celery-scheduler': 3.1, 'worker-periodic': 13.6, 'db': 205.7, 'dragonflydb': 11.0, 'nats': 0.3, 'pfcon': 165.3})_

_Peak disk write at level 8: db 27.1 GiB (per service: {'chris': '1.0 MiB', 'worker-mains': '1.9 GiB', 'worker-periodic': '636.0 KiB', 'db': '27.1 GiB', 'pfcon': '248.0 KiB'})_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132318359552 |
| Docker root | /var/lib/docker |
| Engine | 29.8.2 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 3.6 / 5.8 |

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
| CUBE_DEBUG | false |

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

