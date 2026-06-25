# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T153019Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 5  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| diamond | feeds | 16 | cancelled:inst-4101 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 10.66 | 354.4 | 0 | 18 |  |
| 2 | PASS | 13.59 | 409.5 | 0 | 36 |  |
| 4 | PASS | 14.61 | 427.4 | 0 | 72 |  |
| 8 | PASS | 21.76 | 470.4 | 0 | 144 |  |
| 16 | FAIL | 44.56 | 448.7 | 0 | 287 | cancelled:inst-4101 |

_Peak CPU at level 16: worker-mains 219.2% (per service: {'worker-periodic': 14.7, 'worker-mains': 219.2, 'chris': 64.9, 'celery-scheduler': 1.8, 'pfcon': 17.1, 'db': 173.7, 'nats': 0.0, 'dragonflydb': 7.5})_

_Peak disk write at level 16: db 43.7 MiB (per service: {'worker-periodic': '180.0 KiB', 'worker-mains': '3.0 MiB', 'pfcon': '584.0 KiB', 'db': '43.7 MiB'})_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04 LTS |
| Kernel | 7.0.0-22-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132319051776 |
| Docker root | /var/lib/docker |
| Engine | 27.3.0 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 11.5 / 12.2 |

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

### Manual fields (fill in)

- **storage_device_type_throughput:** TODO
- **power_thermal_mode:** TODO
- **other_significant_workloads:** TODO

