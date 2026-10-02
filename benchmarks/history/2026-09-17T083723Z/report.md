# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T083723Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 5  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| diamond | layers | 16 | scenario_timeout |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.9 | 145.9 | 0 | 6 |  |
| 2 | PASS | 20.16 | 80.1 | 0 | 11 |  |
| 4 | PASS | 41.19 | 87.6 | 0 | 21 |  |
| 8 | PASS | 3216.85 | 1195.5 | 0 | 41 |  |
| 16 | FAIL | 3331.97 | 1861.4 | 0 | 41 | scenario_timeout |

_Peak CPU at level 16: worker-mains 402.5% (per service: {'worker-periodic': 23.5, 'worker-mains': 402.5, 'celery-scheduler': 4.2, 'chris': 77.3, 'db': 220.3, 'nats': 0.2, 'dragonflydb': 16.6, 'pfcon': 6.1})_

_Peak disk write at level 16: db 39.0 GiB (per service: {'worker-periodic': '800.0 KiB', 'worker-mains': '3.0 GiB', 'db': '39.0 GiB', 'pfcon': '264.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.3 / 14.8 |

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

