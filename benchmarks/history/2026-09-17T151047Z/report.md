# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T151047Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 59  •  Breaking points: 5

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| linear | depth | 64 | cancelled:inst-249; cancelled:inst-250; cancelled:inst-251; cancelled:inst-252; cancelled:inst-253; cancelled:inst-254; cancelled:inst-255; cancelled:inst-256; cancelled:inst-257; cancelled:inst-258; cancelled:inst-259; api_5xx:1; no_progress |
| linear | feeds | 64 | cancelled:inst-1897; cancelled:inst-1903 |
| fanout_fanin | feeds | 64 | cancelled:inst-4116; cancelled:inst-4213; cancelled:inst-4234 |
| diamond | layers | 16 | scenario_timeout |
| diamond | feeds | 32 | cancelled:inst-5871 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.4 | 142.2 | 0 | 6 |  |
| 2 | PASS | 12.65 | 89.6 | 0 | 9 |  |
| 4 | PASS | 19.44 | 89.1 | 0 | 15 |  |
| 8 | PASS | 35.45 | 83.5 | 0 | 27 |  |
| 16 | PASS | 67.38 | 172.3 | 0 | 51 |  |
| 32 | PASS | 130.07 | 167.1 | 0 | 99 |  |
| 64 | FAIL | 181.59 | 223.4 | 1 | 41 | cancelled:inst-249; cancelled:inst-250; cancelled:inst-251; cancelled:inst-252; cancelled:inst-253; cancelled:inst-254; cancelled:inst-255; cancelled:inst-256; cancelled:inst-257; cancelled:inst-258; cancelled:inst-259; api_5xx:1; no_progress |

_Peak CPU at level 64: chris 79.2% (per service: {'worker-mains': 29.8, 'worker-periodic': 19.1, 'chris': 79.2, 'celery-scheduler': 3.2, 'db': 28.8, 'nats': 0.1, 'dragonflydb': 18.1, 'pfcon': 3.5})_

_Peak disk write at level 64: db 9.8 MiB (per service: {'worker-mains': '2.3 MiB', 'worker-periodic': '536.0 KiB', 'db': '9.8 MiB', 'pfcon': '308.0 KiB'})_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 21.53 | 75.7 | 0 | 15 |  |
| 10 | PASS | 19.29 | 84.8 | 0 | 15 |  |
| 100 | PASS | 20.47 | 88.8 | 0 | 15 |  |
| 1000 | PASS | 39.67 | 74.8 | 0 | 15 |  |
| 10000 | PASS | 190.97 | 77.8 | 0 | 15 |  |

_Peak CPU at level 10000: worker-mains 101.0% (per service: {'worker-mains': 101.0, 'worker-periodic': 18.6, 'chris': 12.5, 'celery-scheduler': 3.2, 'db': 17.4, 'nats': 0.1, 'dragonflydb': 6.4, 'pfcon': 6.3})_

_Peak disk write at level 10000: db 143.1 MiB (per service: {'worker-mains': '10.9 MiB', 'worker-periodic': '108.0 KiB', 'db': '143.1 MiB', 'pfcon': '32.0 KiB'})_

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.45 | 83.4 | 0 | 15 |  |
| 2 | PASS | 20.52 | 167.4 | 0 | 30 |  |
| 4 | PASS | 19.84 | 184.7 | 0 | 60 |  |
| 8 | PASS | 21.34 | 168.5 | 0 | 120 |  |
| 16 | PASS | 25.23 | 281.3 | 0 | 240 |  |
| 32 | PASS | 47.95 | 546.4 | 0 | 480 |  |
| 64 | FAIL | 117.68 | 993.2 | 0 | 638 | cancelled:inst-1897; cancelled:inst-1903 |

_Peak CPU at level 64: worker-mains 406.6% (per service: {'worker-mains': 406.6, 'worker-periodic': 18.5, 'chris': 85.4, 'celery-scheduler': 3.3, 'db': 137.5, 'nats': 0.0, 'dragonflydb': 8.9, 'pfcon': 66.7})_

_Peak disk write at level 64: db 46.0 MiB (per service: {'worker-mains': '12.0 MiB', 'worker-periodic': '540.0 KiB', 'db': '46.0 MiB', 'pfcon': '2.2 MiB'})_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.7 | 151.2 | 0 | 9 |  |
| 2 | PASS | 11.71 | 77.9 | 0 | 12 |  |
| 4 | PASS | 11.9 | 88.0 | 0 | 18 |  |
| 8 | PASS | 14.4 | 98.8 | 0 | 30 |  |
| 16 | PASS | 14.01 | 86.3 | 0 | 54 |  |
| 32 | PASS | 17.4 | 95.4 | 0 | 102 |  |
| 64 | PASS | 25.44 | 67.0 | 0 | 198 |  |

_Peak CPU at level 64: worker-mains 303.0% (per service: {'worker-mains': 303.0, 'worker-periodic': 17.1, 'chris': 33.6, 'celery-scheduler': 2.5, 'db': 54.7, 'nats': 0.0, 'dragonflydb': 17.7, 'pfcon': 18.8})_

_Peak disk write at level 64: db 8.1 MiB (per service: {'worker-mains': '1.7 MiB', 'worker-periodic': '88.0 KiB', 'db': '8.1 MiB', 'pfcon': '264.0 KiB'})_

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.93 | 112.3 | 0 | 18 |  |
| 2 | PASS | 12.64 | 153.8 | 0 | 36 |  |
| 4 | PASS | 14.1 | 139.1 | 0 | 72 |  |
| 8 | PASS | 18.39 | 200.8 | 0 | 144 |  |
| 16 | PASS | 30.87 | 312.9 | 0 | 288 |  |
| 32 | PASS | 87.11 | 488.5 | 0 | 576 |  |
| 64 | FAIL | 452.23 | 942.1 | 0 | 765 | cancelled:inst-4116; cancelled:inst-4213; cancelled:inst-4234 |

_Peak CPU at level 64: worker-mains 418.6% (per service: {'worker-mains': 418.6, 'worker-periodic': 39.5, 'chris': 86.3, 'celery-scheduler': 3.3, 'db': 212.5, 'nats': 0.2, 'dragonflydb': 18.1, 'pfcon': 51.9})_

_Peak disk write at level 64: db 73.0 MiB (per service: {'worker-mains': '14.9 MiB', 'worker-periodic': '1.0 MiB', 'db': '73.0 MiB', 'pfcon': '2.7 MiB'})_

### fanout_fanin — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.8 | 93.2 | 0 | 18 |  |
| 10 | PASS | 11.89 | 89.0 | 0 | 18 |  |
| 100 | PASS | 12.93 | 89.2 | 0 | 18 |  |
| 1000 | PASS | 21.59 | 88.8 | 0 | 18 |  |
| 10000 | PASS | 87.41 | 85.8 | 0 | 18 |  |

_Peak CPU at level 10000: worker-mains 404.6% (per service: {'worker-mains': 404.6, 'worker-periodic': 20.7, 'chris': 11.2, 'celery-scheduler': 3.4, 'db': 38.9, 'nats': 0.1, 'dragonflydb': 6.1, 'pfcon': 0.0})_

_Peak disk write at level 10000: db 207.7 MiB (per service: {'worker-mains': '9.7 MiB', 'worker-periodic': '60.0 KiB', 'db': '207.7 MiB', 'pfcon': '40.0 KiB'})_

### fanout_fanin — merges

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.98 | 84.2 | 0 | 18 |  |
| 2 | PASS | 10.83 | 91.8 | 0 | 21 |  |
| 4 | PASS | 10.95 | 85.1 | 0 | 27 |  |
| 8 | PASS | 13.36 | 105.5 | 0 | 39 |  |

_Peak CPU at level 8: db 31.2% (per service: {'worker-mains': 9.7, 'worker-periodic': 9.2, 'chris': 14.2, 'celery-scheduler': 0.0, 'db': 31.2, 'nats': 0.1, 'dragonflydb': 4.9, 'pfcon': 0.3})_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.64 | 87.3 | 0 | 9 |  |
| 2 | PASS | 12.84 | 85.7 | 0 | 12 |  |
| 4 | PASS | 10.89 | 81.3 | 0 | 18 |  |
| 8 | PASS | 13.31 | 92.7 | 0 | 30 |  |
| 16 | PASS | 13.77 | 74.1 | 0 | 54 |  |
| 32 | PASS | 16.12 | 86.8 | 0 | 102 |  |

_Peak CPU at level 32: db 98.9% (per service: {'worker-mains': 40.6, 'worker-periodic': 18.8, 'chris': 25.2, 'celery-scheduler': 2.7, 'db': 98.9, 'nats': 0.0, 'dragonflydb': 6.5, 'pfcon': 3.5})_

_Peak disk write at level 32: worker-mains 1.3 MiB (per service: {'worker-mains': '1.3 MiB', 'worker-periodic': '80.0 KiB'})_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.97 | 82.3 | 0 | 18 |  |
| 2 | PASS | 20.06 | 86.6 | 0 | 33 |  |
| 4 | PASS | 41.16 | 90.5 | 0 | 63 |  |
| 8 | PASS | 3392.65 | 1580.0 | 0 | 123 |  |
| 16 | FAIL | 3438.12 | 1726.8 | 0 | 41 | scenario_timeout |

_Peak CPU at level 16: worker-mains 403.4% (per service: {'worker-mains': 403.4, 'worker-periodic': 24.3, 'chris': 79.3, 'celery-scheduler': 6.3, 'db': 210.2, 'nats': 0.1, 'dragonflydb': 16.8, 'pfcon': 5.9})_

_Peak disk write at level 16: db 43.1 GiB (per service: {'worker-mains': '2.5 GiB', 'worker-periodic': '848.0 KiB', 'db': '43.1 GiB', 'pfcon': '264.0 KiB'})_

### diamond — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.95 | 1982.1 | 0 | 18 |  |
| 2 | PASS | 12.38 | 609.1 | 0 | 36 |  |
| 4 | PASS | 14.85 | 644.8 | 0 | 72 |  |
| 8 | PASS | 19.63 | 656.1 | 0 | 144 |  |
| 16 | PASS | 30.12 | 567.8 | 0 | 288 |  |
| 32 | FAIL | 135.83 | 711.7 | 0 | 383 | cancelled:inst-5871 |

_Peak CPU at level 32: worker-mains 410.9% (per service: {'worker-mains': 410.9, 'worker-periodic': 25.3, 'chris': 83.0, 'celery-scheduler': 3.3, 'db': 215.2, 'nats': 0.1, 'dragonflydb': 13.2, 'pfcon': 68.2})_

_Peak disk write at level 32: db 74.4 MiB (per service: {'worker-mains': '7.5 MiB', 'worker-periodic': '732.0 KiB', 'db': '74.4 MiB', 'pfcon': '1.2 MiB'})_

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
| Noise floor (health p50/p95 ms) | 13.2 / 15.9 |

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

