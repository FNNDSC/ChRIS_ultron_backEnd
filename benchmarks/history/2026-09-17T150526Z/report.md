# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T150526Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 91.79 | 551.0 | 0 | 2 |  |
| 2 | PASS | 11.7 | 103.4 | 0 | 3 |  |

_Peak CPU at level 2: dragonflydb 19.1% (per service: {'worker-periodic': 17.8, 'worker-mains': 16.0, 'chris': 5.1, 'celery-scheduler': 3.3, 'db': 18.1, 'nats': 0.0, 'dragonflydb': 19.1, 'pfcon': 0.0})_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.43 | 121.3 | 0 | 2 |  |
| 10 | PASS | 9.47 | 65.6 | 0 | 2 |  |

_Peak CPU at level 10: db 18.1% (per service: {'worker-periodic': 10.2, 'worker-mains': 9.5, 'chris': 5.5, 'celery-scheduler': 3.4, 'db': 18.1, 'nats': 0.1, 'dragonflydb': 8.4, 'pfcon': 0.0})_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.63 | 63.9 | 0 | 3 |  |
| 2 | PASS | 10.75 | 82.6 | 0 | 4 |  |

_Peak CPU at level 2: worker-mains 18.9% (per service: {'worker-periodic': 10.0, 'worker-mains': 18.9, 'chris': 6.6, 'celery-scheduler': 3.4, 'db': 15.8, 'nats': 0.0, 'dragonflydb': 8.5, 'pfcon': 0.0})_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.63 | 95.1 | 0 | 3 |  |
| 2 | PASS | 11.72 | 86.8 | 0 | 4 |  |

_Peak CPU at level 2: db 17.2% (per service: {'worker-periodic': 4.0, 'worker-mains': 0.3, 'chris': 5.8, 'celery-scheduler': 2.1, 'db': 17.2, 'nats': 0.1, 'dragonflydb': 8.3, 'pfcon': 0.0})_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.69 | 79.5 | 0 | 3 |  |
| 2 | PASS | 19.45 | 83.1 | 0 | 5 |  |

_Peak CPU at level 2: worker-mains 18.6% (per service: {'worker-periodic': 17.2, 'worker-mains': 18.6, 'chris': 9.2, 'celery-scheduler': 2.9, 'db': 17.4, 'nats': 0.1, 'dragonflydb': 6.4, 'pfcon': 0.0})_

_Peak disk write at level 2: db 536.0 KiB (per service: {'worker-periodic': '52.0 KiB', 'worker-mains': '216.0 KiB', 'db': '536.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 11.1 / 24.7 |

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

