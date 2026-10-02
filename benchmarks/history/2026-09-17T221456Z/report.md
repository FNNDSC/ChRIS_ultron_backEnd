# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T221456Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 7  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | branches | 64 | cancelled:inst-141 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 21.1 | 133.8 | 0 | 3 |  |
| 2 | PASS | 20.18 | 80.9 | 0 | 4 |  |
| 4 | PASS | 20.63 | 72.3 | 0 | 6 |  |
| 8 | PASS | 25.5 | 65.0 | 0 | 10 |  |
| 16 | PASS | 33.46 | 96.0 | 0 | 18 |  |
| 32 | PASS | 58.66 | 67.6 | 0 | 34 |  |
| 64 | FAIL | 93.82 | 58.2 | 0 | 65 | cancelled:inst-141 |

_Peak CPU at level 64: worker-mains 397.9% (per service: {'celery-scheduler': 2.6, 'worker-mains': 397.9, 'chris': 47.4, 'worker-periodic': 15.3, 'db': 168.6, 'dragonflydb': 8.2, 'nats': 0.1, 'pfcon': 12.2})_

_Peak disk write at level 64: db 180.5 MiB (per service: {'worker-mains': '17.4 MiB', 'worker-periodic': '180.0 KiB', 'db': '180.5 MiB', 'pfcon': '276.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.0 / 15.6 |

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

