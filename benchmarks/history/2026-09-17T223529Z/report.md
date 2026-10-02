# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T223529Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 5  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 13.01 | 130.7 | 0 | 6 |  |
| 2 | PASS | 11.42 | 297.3 | 0 | 12 |  |
| 4 | PASS | 15.17 | 138.8 | 0 | 24 |  |
| 8 | PASS | 18.54 | 170.5 | 0 | 48 |  |
| 16 | PASS | 133.24 | 268.5 | 0 | 96 |  |

_Peak CPU at level 16: worker-mains 406.1% (per service: {'chris': 83.8, 'worker-mains': 406.1, 'celery-scheduler': 3.5, 'worker-periodic': 28.0, 'db': 193.4, 'dragonflydb': 12.7, 'pfcon': 13.1, 'nats': 0.1})_

_Peak disk write at level 16: db 9.7 MiB (per service: {'worker-mains': '2.7 MiB', 'worker-periodic': '116.0 KiB', 'db': '9.7 MiB', 'pfcon': '456.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.0 / 14.4 |

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

