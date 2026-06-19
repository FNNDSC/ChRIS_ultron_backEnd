# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-06-16T022252Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** f4e27c6 (dirty: true)

Levels run: 52  •  Breaking points: 5

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| linear | depth | 64 | cancelled:inst-249; cancelled:inst-250; cancelled:inst-251; cancelled:inst-252; cancelled:inst-253; cancelled:inst-254; cancelled:inst-255; cancelled:inst-256; cancelled:inst-257; cancelled:inst-258; cancelled:inst-259; api_5xx:1; no_progress |
| linear | feeds | 64 | cancelled:inst-1804; cancelled:inst-1856; cancelled:inst-1895; cancelled:inst-1810; cancelled:inst-1877; cancelled:inst-1916 |
| fanout_fanin | feeds | 16 | cancelled:inst-2799 |
| diamond | layers | 16 | scenario_timeout |
| diamond | feeds | 1 | cancelled:inst-3544; cancelled:inst-3545; cancelled:inst-3546; cancelled:inst-3547; cancelled:inst-3548; cancelled:inst-3549 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.32 | 115.5 | 0 | 6 |  |
| 2 | PASS | 11.61 | 80.6 | 0 | 9 |  |
| 4 | PASS | 20.31 | 76.9 | 0 | 15 |  |
| 8 | PASS | 36.28 | 83.7 | 0 | 27 |  |
| 16 | PASS | 66.89 | 116.9 | 0 | 51 |  |
| 32 | PASS | 130.09 | 155.9 | 0 | 99 |  |
| 64 | FAIL | 182.84 | 215.4 | 1 | 41 | cancelled:inst-249; cancelled:inst-250; cancelled:inst-251; cancelled:inst-252; cancelled:inst-253; cancelled:inst-254; cancelled:inst-255; cancelled:inst-256; cancelled:inst-257; cancelled:inst-258; cancelled:inst-259; api_5xx:1; no_progress |

_Peak CPU at level 64: chris 77.1% (per service: {'worker-periodic': 17.3, 'worker-mains': 26.6, 'chris': 77.1, 'celery-scheduler': 2.7, 'pfcon': 14.4, 'db': 21.8, 'nats': 0.1, 'dragonflydb': 8.5})_

_Peak disk write at level 64: db 10.4 MiB (per service: {'worker-periodic': '808.0 KiB', 'worker-mains': '2.3 MiB', 'pfcon': '316.0 KiB', 'db': '10.4 MiB'})_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.17 | 71.7 | 0 | 15 |  |
| 10 | PASS | 20.24 | 72.0 | 0 | 15 |  |
| 100 | PASS | 20.15 | 170.8 | 0 | 15 |  |
| 1000 | PASS | 40.52 | 80.5 | 0 | 15 |  |
| 10000 | PASS | 198.69 | 64.1 | 0 | 15 |  |

_Peak CPU at level 10000: worker-mains 103.2% (per service: {'worker-periodic': 15.9, 'worker-mains': 103.2, 'chris': 14.8, 'celery-scheduler': 3.1, 'pfcon': 8.1, 'db': 54.3, 'nats': 0.1, 'dragonflydb': 11.0})_

_Peak disk write at level 10000: db 147.0 MiB (per service: {'worker-periodic': '248.0 KiB', 'worker-mains': '8.5 MiB', 'pfcon': '32.0 KiB', 'db': '147.0 MiB'})_

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.26 | 113.1 | 0 | 15 |  |
| 2 | PASS | 20.12 | 101.7 | 0 | 30 |  |
| 4 | PASS | 19.54 | 96.2 | 0 | 60 |  |
| 8 | PASS | 21.73 | 167.5 | 0 | 120 |  |
| 16 | PASS | 31.11 | 272.4 | 0 | 240 |  |
| 32 | PASS | 63.36 | 538.0 | 0 | 480 |  |
| 64 | FAIL | 158.27 | 991.3 | 0 | 634 | cancelled:inst-1804; cancelled:inst-1856; cancelled:inst-1895; cancelled:inst-1810; cancelled:inst-1877; cancelled:inst-1916 |

_Peak CPU at level 64: worker-mains 292.3% (per service: {'worker-periodic': 12.5, 'worker-mains': 292.3, 'chris': 84.8, 'celery-scheduler': 4.0, 'pfcon': 33.3, 'db': 107.3, 'nats': 0.1, 'dragonflydb': 10.2})_

_Peak disk write at level 64: db 50.4 MiB (per service: {'worker-periodic': '740.0 KiB', 'worker-mains': '12.3 MiB', 'pfcon': '2.3 MiB', 'db': '50.4 MiB'})_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.58 | 76.6 | 0 | 9 |  |
| 2 | PASS | 12.68 | 77.0 | 0 | 12 |  |
| 4 | PASS | 11.74 | 70.6 | 0 | 18 |  |
| 8 | PASS | 14.29 | 77.6 | 0 | 30 |  |
| 16 | PASS | 12.58 | 77.5 | 0 | 54 |  |
| 32 | PASS | 18.9 | 133.1 | 0 | 102 |  |
| 64 | PASS | 34.28 | 81.0 | 0 | 198 |  |

_Peak CPU at level 64: worker-mains 267.6% (per service: {'worker-periodic': 15.2, 'worker-mains': 267.6, 'chris': 38.3, 'celery-scheduler': 2.9, 'pfcon': 17.5, 'db': 47.0, 'nats': 0.0, 'dragonflydb': 10.9})_

_Peak disk write at level 64: db 6.8 MiB (per service: {'worker-periodic': '164.0 KiB', 'worker-mains': '2.7 MiB', 'pfcon': '368.0 KiB', 'db': '6.8 MiB'})_

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.72 | 73.5 | 0 | 18 |  |
| 2 | PASS | 13.45 | 128.8 | 0 | 36 |  |
| 4 | PASS | 14.8 | 171.3 | 0 | 72 |  |
| 8 | PASS | 21.32 | 153.8 | 0 | 144 |  |
| 16 | FAIL | 41.91 | 354.9 | 0 | 191 | cancelled:inst-2799 |

_Peak CPU at level 16: worker-mains 386.4% (per service: {'worker-periodic': 13.6, 'worker-mains': 386.4, 'chris': 64.6, 'celery-scheduler': 3.9, 'pfcon': 59.5, 'db': 71.9, 'nats': 0.0, 'dragonflydb': 11.2})_

_Peak disk write at level 16: db 12.2 MiB (per service: {'worker-periodic': '188.0 KiB', 'worker-mains': '3.2 MiB', 'pfcon': '576.0 KiB', 'db': '12.2 MiB'})_

### fanout_fanin — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.74 | 86.1 | 0 | 18 |  |
| 10 | PASS | 11.88 | 82.5 | 0 | 18 |  |
| 100 | PASS | 12.75 | 62.5 | 0 | 18 |  |
| 1000 | PASS | 20.4 | 117.4 | 0 | 18 |  |
| 10000 | PASS | 90.85 | 87.9 | 0 | 18 |  |

_Peak CPU at level 10000: worker-mains 403.4% (per service: {'worker-periodic': 14.7, 'worker-mains': 403.4, 'chris': 8.7, 'celery-scheduler': 3.3, 'pfcon': 1.1, 'db': 15.7, 'nats': 0.1, 'dragonflydb': 5.2})_

_Peak disk write at level 10000: db 204.2 MiB (per service: {'worker-periodic': '128.0 KiB', 'worker-mains': '9.8 MiB', 'pfcon': '44.0 KiB', 'db': '204.2 MiB'})_

### fanout_fanin — merges

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.83 | 89.5 | 0 | 18 |  |
| 2 | PASS | 12.85 | 107.9 | 0 | 21 |  |
| 4 | PASS | 10.89 | 78.7 | 0 | 27 |  |
| 8 | PASS | 13.42 | 75.8 | 0 | 39 |  |

_Peak CPU at level 8: db 16.2% (per service: {'worker-periodic': 5.9, 'worker-mains': 0.7, 'chris': 10.2, 'celery-scheduler': 0.0, 'pfcon': 8.5, 'db': 16.2, 'nats': 0.0, 'dragonflydb': 4.2})_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.57 | 85.7 | 0 | 9 |  |
| 2 | PASS | 11.65 | 69.9 | 0 | 12 |  |
| 4 | PASS | 12.86 | 74.1 | 0 | 18 |  |
| 8 | PASS | 13.19 | 150.9 | 0 | 30 |  |
| 16 | PASS | 13.78 | 73.3 | 0 | 54 |  |
| 32 | PASS | 18.65 | 78.1 | 0 | 102 |  |

_Peak CPU at level 32: db 105.9% (per service: {'worker-periodic': 14.8, 'worker-mains': 27.9, 'chris': 30.3, 'celery-scheduler': 2.7, 'pfcon': 14.5, 'db': 105.9, 'nats': 0.0, 'dragonflydb': 5.3})_

_Peak disk write at level 32: db 3.6 MiB (per service: {'worker-periodic': '72.0 KiB', 'worker-mains': '1.3 MiB', 'pfcon': '140.0 KiB', 'db': '3.6 MiB'})_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.8 | 105.4 | 0 | 18 |  |
| 2 | PASS | 20.12 | 78.6 | 0 | 33 |  |
| 4 | PASS | 42.19 | 100.4 | 0 | 63 |  |
| 8 | DEGRADED | 3458.12 | 2066.4 | 0 | 123 | p95_latency:2066ms>2000ms |
| 16 | FAIL | 3462.99 | 1490.4 | 0 | 41 | scenario_timeout |

_Peak CPU at level 16: worker-mains 406.4% (per service: {'worker-periodic': 20.3, 'worker-mains': 406.4, 'chris': 74.0, 'celery-scheduler': 3.9, 'pfcon': 120.1, 'db': 205.9, 'nats': 0.1, 'dragonflydb': 10.8}); plugin-jobs peak 73.3%_

_Peak disk write at level 16: db 46.6 GiB (per service: {'worker-periodic': '3.3 MiB', 'worker-mains': '3.3 GiB', 'pfcon': '288.0 KiB', 'db': '46.6 GiB'})_

### diamond — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | FAIL | 142.08 | 1691.7 | 0 | 0 | cancelled:inst-3544; cancelled:inst-3545; cancelled:inst-3546; cancelled:inst-3547; cancelled:inst-3548; cancelled:inst-3549 |

_Peak CPU at level 1: worker-mains 406.7% (per service: {'worker-periodic': 18.6, 'worker-mains': 406.7, 'chris': 9.4, 'celery-scheduler': 3.7, 'pfcon': 0.0, 'db': 182.0, 'nats': 0.1, 'dragonflydb': 11.6})_

_Peak disk write at level 1: db 385.6 MiB (per service: {'worker-periodic': '116.0 KiB', 'worker-mains': '96.0 KiB', 'pfcon': '4.0 KiB', 'db': '385.6 MiB'})_

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
| Noise floor (health p50/p95 ms) | 9.6 / 12.9 |

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

