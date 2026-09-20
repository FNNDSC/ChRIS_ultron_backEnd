# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T223926Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 5  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | feeds | 16 | cancelled:inst-313; cancelled:inst-338; cancelled:inst-354; cancelled:inst-344; cancelled:inst-355; cancelled:inst-345; cancelled:inst-356; cancelled:inst-339; cancelled:inst-350; cancelled:inst-361; cancelled:inst-342; cancelled:inst-353; cancelled:inst-364; cancelled:inst-335; cancelled:inst-349; cancelled:inst-358; cancelled:inst-369; cancelled:inst-337; cancelled:inst-348; cancelled:inst-359; cancelled:inst-367; cancelled:inst-336; cancelled:inst-351; cancelled:inst-372 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 10.85 | 134.7 | 0 | 6 |  |
| 2 | PASS | 11.54 | 203.5 | 0 | 12 |  |
| 4 | PASS | 13.73 | 131.0 | 0 | 24 |  |
| 8 | PASS | 17.52 | 174.9 | 0 | 48 |  |
| 16 | FAIL | 34.52 | 322.5 | 0 | 72 | cancelled:inst-313; cancelled:inst-338; cancelled:inst-354; cancelled:inst-344; cancelled:inst-355; cancelled:inst-345; cancelled:inst-356; cancelled:inst-339; cancelled:inst-350; cancelled:inst-361; cancelled:inst-342; cancelled:inst-353; cancelled:inst-364; cancelled:inst-335; cancelled:inst-349; cancelled:inst-358; cancelled:inst-369; cancelled:inst-337; cancelled:inst-348; cancelled:inst-359; cancelled:inst-367; cancelled:inst-336; cancelled:inst-351; cancelled:inst-372 |

_Peak CPU at level 16: worker-mains 403.6% (per service: {'chris': 88.1, 'worker-mains': 403.6, 'celery-scheduler': 3.4, 'worker-periodic': 15.9, 'db': 92.1, 'dragonflydb': 7.5, 'pfcon': 195.0, 'nats': 0.1})_

_Peak disk write at level 16: db 12.2 MiB (per service: {'worker-mains': '2.5 MiB', 'worker-periodic': '104.0 KiB', 'db': '12.2 MiB', 'pfcon': '284.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.5 / 14.3 |

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

