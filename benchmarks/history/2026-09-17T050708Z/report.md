# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T050708Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 8  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 19.34 | 143.4 | 0 | 5 |  |
| 2 | PASS | 19.22 | 119.5 | 0 | 10 |  |
| 4 | PASS | 19.66 | 204.0 | 0 | 20 |  |
| 8 | PASS | 19.29 | 210.6 | 0 | 40 |  |
| 16 | PASS | 27.9 | 247.7 | 0 | 80 |  |
| 32 | PASS | 45.32 | 557.9 | 0 | 160 |  |
| 64 | PASS | 115.92 | 1091.6 | 0 | 320 |  |
| 128 | PASS | 527.44 | 1767.7 | 0 | 640 |  |

_Peak CPU at level 128: worker-mains 405.9% (per service: {'worker-mains': 405.9, 'worker-periodic': 22.3, 'chris': 366.4, 'celery-scheduler': 3.3, 'db': 207.6, 'nats': 0.0, 'dragonflydb': 18.3, 'pfcon': 50.3})_

_Peak disk write at level 128: db 111.8 MiB (per service: {'worker-mains': '24.1 MiB', 'worker-periodic': '2.0 MiB', 'db': '111.8 MiB', 'pfcon': '4.5 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.4 / 15.3 |

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

