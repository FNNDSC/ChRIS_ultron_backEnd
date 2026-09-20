# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T040629Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.37 | 163.3 | 0 | 2 |  |
| 2 | PASS | 12.68 | 74.4 | 0 | 3 |  |

_Peak CPU at level 2: worker-periodic 17.7% (per service: {'worker-mains': 13.0, 'celery-scheduler': 3.1, 'chris': 6.7, 'worker-periodic': 17.7, 'dragonflydb': 6.6, 'db': 16.9, 'pfcon': 7.6, 'nats': 0.1})_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.4 | 69.0 | 0 | 2 |  |
| 10 | PASS | 7.33 | 236.6 | 0 | 2 |  |

_Peak CPU at level 10: worker-periodic 17.2% (per service: {'worker-mains': 16.5, 'celery-scheduler': 2.9, 'chris': 5.0, 'worker-periodic': 17.2, 'dragonflydb': 8.3, 'db': 14.6, 'pfcon': 0.0})_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.64 | 73.7 | 0 | 3 |  |
| 2 | PASS | 11.77 | 73.3 | 0 | 4 |  |

_Peak CPU at level 2: db 13.6% (per service: {'worker-mains': 7.6, 'celery-scheduler': 0.0, 'chris': 6.3, 'worker-periodic': 8.1, 'dragonflydb': 6.1, 'db': 13.6, 'pfcon': 0.0, 'nats': 0.1})_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.65 | 75.4 | 0 | 3 |  |
| 2 | PASS | 11.72 | 78.0 | 0 | 4 |  |

_Peak CPU at level 2: db 15.0% (per service: {'worker-mains': 8.4, 'celery-scheduler': 0.0, 'chris': 5.7, 'worker-periodic': 8.1, 'dragonflydb': 5.4, 'db': 15.0, 'pfcon': 0.1, 'nats': 0.1})_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.73 | 66.6 | 0 | 3 |  |
| 2 | PASS | 20.39 | 67.1 | 0 | 5 |  |

_Peak CPU at level 2: worker-periodic 18.9% (per service: {'worker-mains': 12.6, 'celery-scheduler': 2.8, 'chris': 10.7, 'worker-periodic': 18.9, 'dragonflydb': 8.3, 'db': 18.3, 'pfcon': 3.2, 'nats': 0.1})_

_Peak disk write at level 2: worker-mains 196.0 KiB (per service: {'worker-mains': '196.0 KiB', 'worker-periodic': '40.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.4 / 14.8 |

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

