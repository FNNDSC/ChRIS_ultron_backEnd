# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T120620Z  •  **Tier:** aging-grow  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 3  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 146.84 | 75.6 | 0 | 8 |  |
| 2 | PASS | 149.53 | 86.2 | 0 | 16 |  |
| 4 | PASS | 154.42 | 132.8 | 0 | 32 |  |

_Peak CPU at level 4: worker-mains 402.2% (per service: {'worker-periodic': 18.4, 'worker-mains': 402.2, 'chris': 28.2, 'celery-scheduler': 3.6, 'db': 134.3, 'nats': 0.1, 'dragonflydb': 5.0, 'pfcon': 9.2})_

_Peak disk write at level 4: db 337.7 MiB (per service: {'worker-periodic': '144.0 KiB', 'worker-mains': '33.3 MiB', 'db': '337.7 MiB', 'pfcon': '116.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.3 / 15.6 |

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

