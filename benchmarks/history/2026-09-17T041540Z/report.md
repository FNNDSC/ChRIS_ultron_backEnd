# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T041540Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 6  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 19.37 | 79.5 | 0 | 5 |  |
| 10 | PASS | 20.41 | 83.5 | 0 | 5 |  |
| 100 | PASS | 20.38 | 73.1 | 0 | 5 |  |
| 1000 | PASS | 36.59 | 71.5 | 0 | 5 |  |
| 10000 | PASS | 189.65 | 81.4 | 0 | 5 |  |
| 100000 | PASS | 1766.42 | 68.9 | 0 | 5 |  |

_Peak CPU at level 100000: db 113.3% (per service: {'worker-mains': 108.7, 'celery-scheduler': 3.1, 'chris': 13.3, 'worker-periodic': 16.5, 'dragonflydb': 16.6, 'db': 113.3, 'pfcon': 1.9, 'nats': 0.1})_

_Peak disk write at level 100000: db 1.1 GiB (per service: {'worker-mains': '78.9 MiB', 'worker-periodic': '328.0 KiB', 'db': '1.1 GiB', 'pfcon': '36.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.0 / 15.2 |

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

