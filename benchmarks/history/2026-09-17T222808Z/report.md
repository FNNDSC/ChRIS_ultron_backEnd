# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T222808Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 7  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | branches | 64 | cancelled:inst-423 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 17.91 | 96.8 | 0 | 3 |  |
| 2 | PASS | 18.06 | 82.6 | 0 | 4 |  |
| 4 | PASS | 20.5 | 94.9 | 0 | 6 |  |
| 8 | PASS | 53.51 | 60.8 | 0 | 10 |  |
| 16 | PASS | 33.39 | 87.7 | 0 | 18 |  |
| 32 | PASS | 57.56 | 74.6 | 0 | 34 |  |
| 64 | FAIL | 94.52 | 62.8 | 0 | 65 | cancelled:inst-423 |

_Peak CPU at level 64: worker-mains 423.1% (per service: {'celery-scheduler': 3.3, 'worker-mains': 423.1, 'chris': 33.9, 'worker-periodic': 15.1, 'db': 189.9, 'dragonflydb': 9.8, 'nats': 0.1, 'pfcon': 12.2})_

_Peak disk write at level 64: db 112.9 MiB (per service: {'worker-mains': '17.4 MiB', 'worker-periodic': '172.0 KiB', 'db': '112.9 MiB', 'pfcon': '324.0 KiB'})_

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

