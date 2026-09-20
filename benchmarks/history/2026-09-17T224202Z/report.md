# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-09-17T224202Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 30fbbaf (dirty: true)

Levels run: 5  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | feeds | 16 | cancelled:inst-530; cancelled:inst-544; cancelled:inst-533; cancelled:inst-545; cancelled:inst-538; cancelled:inst-547; cancelled:inst-540; cancelled:inst-548; cancelled:inst-531; cancelled:inst-543; cancelled:inst-549; cancelled:inst-536; cancelled:inst-552; cancelled:inst-535; cancelled:inst-553; cancelled:inst-492; cancelled:inst-505; cancelled:inst-524; cancelled:inst-539; cancelled:inst-555; cancelled:inst-534; cancelled:inst-550; cancelled:inst-556; cancelled:inst-532; cancelled:inst-551; cancelled:inst-557; cancelled:inst-528; cancelled:inst-542; cancelled:inst-554; cancelled:inst-558 |

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.8 | 129.1 | 0 | 6 |  |
| 2 | PASS | 13.59 | 209.8 | 0 | 12 |  |
| 4 | PASS | 13.63 | 276.5 | 0 | 24 |  |
| 8 | PASS | 18.56 | 144.5 | 0 | 48 |  |
| 16 | FAIL | 67.56 | 282.5 | 0 | 66 | cancelled:inst-530; cancelled:inst-544; cancelled:inst-533; cancelled:inst-545; cancelled:inst-538; cancelled:inst-547; cancelled:inst-540; cancelled:inst-548; cancelled:inst-531; cancelled:inst-543; cancelled:inst-549; cancelled:inst-536; cancelled:inst-552; cancelled:inst-535; cancelled:inst-553; cancelled:inst-492; cancelled:inst-505; cancelled:inst-524; cancelled:inst-539; cancelled:inst-555; cancelled:inst-534; cancelled:inst-550; cancelled:inst-556; cancelled:inst-532; cancelled:inst-551; cancelled:inst-557; cancelled:inst-528; cancelled:inst-542; cancelled:inst-554; cancelled:inst-558 |

_Peak CPU at level 16: chris 301.4% (per service: {'chris': 301.4, 'worker-mains': 172.6, 'celery-scheduler': 3.3, 'worker-periodic': 21.5, 'db': 189.1, 'dragonflydb': 11.0, 'pfcon': 21.8, 'nats': 0.1})_

_Peak disk write at level 16: db 8.2 MiB (per service: {'worker-mains': '2.3 MiB', 'worker-periodic': '104.0 KiB', 'db': '8.2 MiB', 'pfcon': '224.0 KiB'})_

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
| Noise floor (health p50/p95 ms) | 13.6 / 15.3 |

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

