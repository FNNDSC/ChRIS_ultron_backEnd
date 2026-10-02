# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T110245Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 8  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| linear | feeds | 128 | cancelled:inst-2530 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.4 | 210.8 | 0 | 15 |  |
| 2 | PASS | 19.34 | 145.3 | 0 | 30 |  |
| 4 | PASS | 19.93 | 115.8 | 0 | 60 |  |
| 8 | PASS | 21.37 | 186.7 | 0 | 120 |  |
| 16 | PASS | 25.99 | 297.6 | 0 | 240 |  |
| 32 | PASS | 44.24 | 738.0 | 0 | 480 |  |
| 64 | PASS | 120.78 | 970.7 | 0 | 960 |  |
| 128 | FAIL | 513.85 | 1835.7 | 0 | 639 | cancelled:inst-2530 |

_Peak CPU at level 128: worker-mains 412.9% (per service: {'chris': 402.2, 'worker-periodic': 21.8, 'worker-mains': 412.9, 'celery-scheduler': 3.4, 'nats': 0.0, 'pfcon': 68.5, 'db': 202.7, 'dragonflydb': 17.5})_

_Peak disk write at level 128: db 112.3 MiB (per service: {'worker-periodic': '2.1 MiB', 'worker-mains': '23.8 MiB', 'pfcon': '4.7 MiB', 'db': '112.3 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.4 / 15.6 |

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

