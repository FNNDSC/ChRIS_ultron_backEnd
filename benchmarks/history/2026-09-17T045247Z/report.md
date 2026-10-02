# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T045247Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 7  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| linear | depth | 64 | cancelled:inst-197; cancelled:inst-198; cancelled:inst-199; cancelled:inst-200; cancelled:inst-201; cancelled:inst-202; cancelled:inst-203; cancelled:inst-204; cancelled:inst-205; cancelled:inst-206; cancelled:inst-207; api_5xx:1; no_progress |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 7.35 | 81.4 | 0 | 2 |  |
| 2 | PASS | 12.69 | 87.6 | 0 | 3 |  |
| 4 | PASS | 20.43 | 67.7 | 0 | 5 |  |
| 8 | PASS | 35.39 | 72.5 | 0 | 9 |  |
| 16 | PASS | 66.81 | 108.5 | 0 | 17 |  |
| 32 | PASS | 130.82 | 161.8 | 0 | 33 |  |
| 64 | FAIL | 183.08 | 203.5 | 1 | 41 | cancelled:inst-197; cancelled:inst-198; cancelled:inst-199; cancelled:inst-200; cancelled:inst-201; cancelled:inst-202; cancelled:inst-203; cancelled:inst-204; cancelled:inst-205; cancelled:inst-206; cancelled:inst-207; api_5xx:1; no_progress |

_Peak CPU at level 64: chris 83.7% (per service: {'worker-mains': 37.8, 'celery-scheduler': 3.3, 'chris': 83.7, 'worker-periodic': 17.4, 'dragonflydb': 18.2, 'db': 29.9, 'pfcon': 3.1, 'nats': 0.1})_

_Peak disk write at level 64: db 42.6 MiB (per service: {'worker-mains': '2.3 MiB', 'worker-periodic': '532.0 KiB', 'db': '42.6 MiB', 'pfcon': '312.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.1 / 14.2 |

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

