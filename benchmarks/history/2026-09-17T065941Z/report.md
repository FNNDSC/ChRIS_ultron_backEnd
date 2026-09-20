# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T065941Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 6  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | branches | 32 | cancelled:inst-75 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.06 | 157.5 | 0 | 3 |  |
| 2 | PASS | 20.26 | 77.7 | 0 | 4 |  |
| 4 | PASS | 20.52 | 77.4 | 0 | 6 |  |
| 8 | PASS | 26.48 | 83.8 | 0 | 10 |  |
| 16 | PASS | 33.4 | 65.6 | 0 | 18 |  |
| 32 | FAIL | 44.42 | 73.0 | 0 | 33 | cancelled:inst-75 |

_Peak CPU at level 32: worker-mains 401.7% (per service: {'celery-scheduler': 2.3, 'worker-periodic': 14.0, 'worker-mains': 401.7, 'chris': 24.6, 'nats': 0.0, 'db': 38.5, 'dragonflydb': 8.0, 'pfcon': 0.0})_

_Peak disk write at level 32: db 53.4 MiB (per service: {'worker-periodic': '56.0 KiB', 'worker-mains': '5.9 MiB', 'db': '53.4 MiB', 'pfcon': '132.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.2 / 15.4 |

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

