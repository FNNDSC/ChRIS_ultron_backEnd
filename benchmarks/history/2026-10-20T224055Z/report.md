# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-20T224055Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 5bc2e49 (dirty: true)

Levels run: 7  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| fanout_fanin | feeds | 64 | cancelled:inst-725 |

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 29.2 MiB (143 full-page images), temp files 0 B, db container wrote 199.9 MiB, WAL segments zero-filled 32.0 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### fanout_fanin — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.48 | 90.3 | 0 | 6 |  |
| 2 | PASS | 11.96 | 71.4 | 0 | 12 |  |
| 4 | PASS | 13.96 | 255.5 | 0 | 24 |  |
| 8 | PASS | 17.52 | 87.7 | 0 | 48 |  |
| 16 | PASS | 27.31 | 223.0 | 0 | 96 |  |
| 32 | PASS | 70.2 | 489.8 | 0 | 192 |  |
| 64 | FAIL | 239.5 | 889.9 | 0 | 383 | cancelled:inst-725 |

_Peak CPU at level 64: worker-mains 419.6% (per service: {'worker-periodic': 28.6, 'celery-scheduler': 2.7, 'worker-mains': 419.6, 'chris': 85.1, 'db': 190.0, 'dragonflydb': 14.4, 'nats': 0.1, 'pfcon': 32.9})_

_Peak disk write at level 64: db 78.7 MiB (per service: {'worker-periodic': '824.0 KiB', 'worker-mains': '14.5 MiB', 'chris': '268.0 KiB', 'db': '78.7 MiB', 'pfcon': '2.7 MiB'})_

_Postgres at level 64: workload checkpoints 0 done (0 timed / 0 requested), WAL 14.2 MiB (19 full-page images), temp files 0 B, db container wrote 98.2 MiB, WAL segments zero-filled 16.0 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 457.5 KiB (0 full-page images), temp files 0 B, db container wrote 1.5 MiB_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132318351360 |
| Docker root | /var/lib/docker |
| Engine | 29.9.1 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 4.5 / 6.3 |

### Envelope (recorded knobs)

| Knob | Value |
|---|---|
| CUBE_CELERY_POLL_INTERVAL | 2.0 |
| CUBE_UVICORN_WORKERS | 4 |
| CUBE_DB_POOL_MIN_SIZE | 2 |
| CUBE_DB_POOL_MAX_SIZE | 10 |
| CUBE_DB_POOL_TIMEOUT | 10 |
| CUBE_DB_MAX_CONNECTIONS | 300 |
| CUBE_DB_SYNCHRONOUS_COMMIT | on |
| CUBE_WORKER_MAINS_CONCURRENCY | 4 |
| PFCON_WORKERS | 8 |
| STORAGE_ENV | fslink |
| CUBE_DEBUG | false |

### Container limits (as applied)

| Service | CPUs | Memory | Memory + swap | /dev/shm |
|---|---|---|---|---|
| celery-scheduler | — | — | — | 64.0 MiB |
| chris | 4.0 | 4.0 GiB | 8.0 GiB | 64.0 MiB |
| db | 2.0 | 4.0 GiB | 8.0 GiB | 1.0 GiB |
| dragonflydb | — | — | — | 64.0 MiB |
| nats | — | — | — | 64.0 MiB |
| pfcon | 2.0 | 2.0 GiB | 4.0 GiB | 64.0 MiB |
| worker-mains | 4.0 | 4.0 GiB | 8.0 GiB | 64.0 MiB |
| worker-periodic | — | — | — | 64.0 MiB |

### PostgreSQL (key settings; environment.json has all)

| Setting | Value |
|---|---|
| autovacuum_max_workers | 3 |
| checkpoint_completion_target | 0.9 |
| checkpoint_timeout | 15min |
| config_file | /etc/postgresql/cube.conf |
| data_checksums | on |
| DateStyle | ISO, MDY |
| default_text_search_config | pg_catalog.english |
| dynamic_shared_memory_type | posix |
| effective_cache_size | 3GB |
| effective_io_concurrency | 200 |
| full_page_writes | on |
| hash_mem_multiplier | 2 |
| io_method | worker |
| io_workers | 3 |
| jit | on |
| lc_messages | en_US.utf8 |
| lc_monetary | en_US.utf8 |
| lc_numeric | en_US.utf8 |
| lc_time | en_US.utf8 |
| listen_addresses | * |
| log_lock_waits | on |
| log_min_duration_statement | 1s |
| log_timezone | UTC |
| maintenance_work_mem | 512MB |
| max_connections | 300 |
| max_parallel_workers_per_gather | 2 |
| max_wal_size | 8GB |
| min_wal_size | 1GB |
| random_page_cost | 1.1 |
| server_version | 18.2 (Debian 18.2-1.pgdg13+1) |
| shared_buffers | 1GB |
| shared_preload_libraries | pg_stat_statements |
| synchronous_commit | on |
| TimeZone | UTC |
| track_io_timing | on |
| wal_buffers | 16MB |
| wal_compression | lz4 |
| wal_level | replica |
| work_mem | 32MB |

_`core_chrisfile` storage parameters: autovacuum_vacuum_scale_factor=0.02, autovacuum_analyze_scale_factor=0.01_

_`core_chrisfolder` storage parameters: autovacuum_vacuum_scale_factor=0.02, autovacuum_analyze_scale_factor=0.01_

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

