# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T113103Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 6  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | feeds | 32 | cancelled:inst-690 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.92 | 151.5 | 0 | 18 |  |
| 2 | PASS | 13.73 | 204.6 | 0 | 36 |  |
| 4 | PASS | 13.82 | 136.8 | 0 | 72 |  |
| 8 | PASS | 17.53 | 170.1 | 0 | 144 |  |
| 16 | PASS | 29.0 | 264.4 | 0 | 288 |  |
| 32 | FAIL | 80.74 | 477.4 | 0 | 191 | cancelled:inst-690 |

_Peak CPU at level 32: worker-mains 271.8% (per service: {'worker-periodic': 22.1, 'celery-scheduler': 3.1, 'worker-mains': 271.8, 'chris': 87.7, 'db': 205.4, 'nats': 0.0, 'dragonflydb': 11.8, 'pfcon': 17.3})_

_Peak disk write at level 32: db 19.4 MiB (per service: {'worker-periodic': '304.0 KiB', 'worker-mains': '5.7 MiB', 'db': '19.4 MiB', 'pfcon': '1.0 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.5 / 15.6 |

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

