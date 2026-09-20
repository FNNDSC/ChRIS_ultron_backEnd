# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T053431Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 6  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| diamond | feeds | 32 | cancelled:inst-2948; cancelled:inst-2952; cancelled:inst-2964 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.92 | 125.2 | 0 | 18 |  |
| 2 | PASS | 12.52 | 209.2 | 0 | 36 |  |
| 4 | PASS | 13.76 | 120.7 | 0 | 72 |  |
| 8 | PASS | 18.76 | 176.5 | 0 | 144 |  |
| 16 | PASS | 29.35 | 406.2 | 0 | 288 |  |
| 32 | FAIL | 80.43 | 562.0 | 0 | 381 | cancelled:inst-2948; cancelled:inst-2952; cancelled:inst-2964 |

_Peak CPU at level 32: worker-mains 413.1% (per service: {'worker-mains': 413.1, 'worker-periodic': 20.3, 'chris': 85.0, 'celery-scheduler': 2.5, 'db': 181.3, 'nats': 0.1, 'dragonflydb': 11.5, 'pfcon': 40.4})_

_Peak disk write at level 32: db 25.7 MiB (per service: {'worker-mains': '7.4 MiB', 'worker-periodic': '376.0 KiB', 'db': '25.7 MiB', 'pfcon': '1.1 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.1 / 14.1 |

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

