# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T070345Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 6  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 10.87 | 126.0 | 0 | 6 |  |
| 10 | PASS | 11.98 | 69.2 | 0 | 6 |  |
| 100 | PASS | 11.79 | 89.4 | 0 | 6 |  |
| 1000 | PASS | 21.64 | 85.1 | 0 | 6 |  |
| 10000 | PASS | 86.63 | 70.1 | 0 | 6 |  |
| 100000 | PASS | 792.91 | 217.5 | 0 | 6 |  |

_Peak CPU at level 100000: worker-mains 417.3% (per service: {'celery-scheduler': 4.1, 'worker-periodic': 21.8, 'worker-mains': 417.3, 'chris': 12.0, 'nats': 0.1, 'db': 199.6, 'dragonflydb': 13.2, 'pfcon': 43.6})_

_Peak disk write at level 100000: db 2.2 GiB (per service: {'worker-periodic': '164.0 KiB', 'worker-mains': '175.7 MiB', 'db': '2.2 GiB', 'pfcon': '44.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 12.7 / 13.8 |

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

