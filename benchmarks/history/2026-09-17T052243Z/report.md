# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T052243Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 7  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.85 | 125.4 | 0 | 6 |  |
| 2 | PASS | 13.56 | 212.0 | 0 | 12 |  |
| 4 | PASS | 13.81 | 299.1 | 0 | 24 |  |
| 8 | PASS | 17.37 | 138.0 | 0 | 48 |  |
| 16 | PASS | 31.25 | 243.4 | 0 | 96 |  |
| 32 | PASS | 83.76 | 554.0 | 0 | 192 |  |
| 64 | PASS | 432.2 | 876.6 | 0 | 384 |  |

_Peak CPU at level 64: worker-mains 418.0% (per service: {'worker-mains': 418.0, 'worker-periodic': 39.9, 'chris': 80.8, 'celery-scheduler': 3.0, 'db': 203.8, 'nats': 0.1, 'dragonflydb': 17.3, 'pfcon': 20.0})_

_Peak disk write at level 64: db 76.9 MiB (per service: {'worker-mains': '15.3 MiB', 'worker-periodic': '940.0 KiB', 'db': '76.9 MiB', 'pfcon': '2.6 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.2 / 15.1 |

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

