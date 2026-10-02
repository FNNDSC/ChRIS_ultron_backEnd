# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T120820Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.36 | 77.6 | 0 | 2 |  |
| 2 | PASS | 12.66 | 87.2 | 0 | 3 |  |

_Peak CPU at level 2: worker-mains 110.8% (per service: {'worker-periodic': 5.6, 'worker-mains': 110.8, 'chris': 12.7, 'celery-scheduler': 0.0, 'db': 14.8, 'nats': 0.0, 'dragonflydb': 5.9, 'pfcon': 1.1})_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.34 | 69.0 | 0 | 2 |  |
| 10 | PASS | 8.37 | 60.5 | 0 | 2 |  |

_Peak CPU at level 10: worker-mains 100.7% (per service: {'worker-periodic': 7.0, 'worker-mains': 100.7, 'chris': 9.9, 'celery-scheduler': 0.0, 'db': 14.9, 'nats': 0.1, 'dragonflydb': 7.9, 'pfcon': 0.0})_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.6 | 64.3 | 0 | 3 |  |
| 2 | PASS | 11.73 | 64.1 | 0 | 4 |  |

_Peak CPU at level 2: worker-mains 201.6% (per service: {'worker-periodic': 6.9, 'worker-mains': 201.6, 'chris': 11.2, 'celery-scheduler': 0.0, 'db': 9.9, 'nats': 0.1, 'dragonflydb': 6.1, 'pfcon': 0.1})_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.58 | 70.0 | 0 | 3 |  |
| 2 | PASS | 12.73 | 81.0 | 0 | 4 |  |

_Peak CPU at level 2: worker-mains 212.0% (per service: {'worker-periodic': 7.1, 'worker-mains': 212.0, 'chris': 9.1, 'celery-scheduler': 1.4, 'db': 18.1, 'nats': 0.0, 'dragonflydb': 4.1, 'pfcon': 25.3})_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 34.73 | 84.7 | 0 | 3 |  |
| 2 | PASS | 45.0 | 76.9 | 0 | 5 |  |

_Peak CPU at level 2: worker-mains 401.7% (per service: {'worker-periodic': 17.1, 'worker-mains': 401.7, 'chris': 24.6, 'celery-scheduler': 2.5, 'db': 18.6, 'nats': 0.1, 'dragonflydb': 8.2, 'pfcon': 0.1})_

_Peak disk write at level 2: db 135.3 MiB (per service: {'worker-periodic': '36.0 KiB', 'worker-mains': '9.4 MiB', 'db': '135.3 MiB', 'pfcon': '56.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 11.4 / 12.6 |

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

