# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-07T002040Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 911fb6c (dirty: true)

Levels run: 6  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.76 | 87.1 | 0 | 5 |  |
| 10 | PASS | 19.77 | 43.0 | 0 | 5 |  |
| 100 | PASS | 19.79 | 39.8 | 0 | 5 |  |
| 1000 | PASS | 37.42 | 44.6 | 0 | 5 |  |
| 10000 | PASS | 188.81 | 39.8 | 0 | 5 |  |
| 100000 | PASS | 1730.86 | 44.9 | 0 | 5 |  |

_Peak CPU at level 100000: db 109.5% (per service: {'chris': 11.9, 'worker-mains': 101.5, 'celery-scheduler': 2.6, 'worker-periodic': 10.3, 'db': 109.5, 'dragonflydb': 10.0, 'nats': 0.1, 'pfcon': 1.0})_

_Peak disk write at level 100000: db 1.1 GiB (per service: {'chris': '692.0 KiB', 'worker-mains': '78.0 MiB', 'worker-periodic': '300.0 KiB', 'db': '1.1 GiB', 'pfcon': '32.0 KiB'})_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132318359552 |
| Docker root | /var/lib/docker |
| Engine | 29.8.2 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 4.0 / 6.3 |

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
| CUBE_DEBUG | false |

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

