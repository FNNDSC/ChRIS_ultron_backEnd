# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T155156Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 7  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| linear | feeds | 64 | cancelled:inst-4595; cancelled:inst-4645; cancelled:inst-4516; cancelled:inst-4596; cancelled:inst-4653 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 259.31 | 308.8 | 0 | 5 |  |
| 2 | PASS | 260.55 | 450.5 | 0 | 10 |  |
| 4 | PASS | 260.46 | 582.4 | 0 | 20 |  |
| 8 | PASS | 261.97 | 467.5 | 0 | 40 |  |
| 16 | PASS | 270.95 | 449.7 | 0 | 80 |  |
| 32 | PASS | 283.46 | 497.6 | 0 | 160 |  |
| 64 | FAIL | 341.56 | 1008.6 | 0 | 315 | cancelled:inst-4595; cancelled:inst-4645; cancelled:inst-4516; cancelled:inst-4596; cancelled:inst-4653 |

_Peak CPU at level 64: worker-mains 225.9% (per service: {'worker-periodic': 16.9, 'worker-mains': 225.9, 'chris': 85.5, 'celery-scheduler': 3.0, 'pfcon': 25.2, 'db': 128.7, 'nats': 0.0, 'dragonflydb': 11.7})_

_Peak disk write at level 64: db 109.8 MiB (per service: {'worker-periodic': '1.0 MiB', 'worker-mains': '20.7 MiB', 'pfcon': '2.2 MiB', 'db': '109.8 MiB'})_

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
| Noise floor (health p50/p95 ms) | 12.8 / 14.4 |

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

