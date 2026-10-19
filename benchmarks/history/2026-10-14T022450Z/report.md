# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-14T022450Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 2d52608 (dirty: false)

Levels run: 6  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 1 done (2 timed / 0 requested), WAL 559.9 MiB (8,139 full-page images), temp files 0 B, db container wrote 1.4 GiB, of which zero-filling new WAL segments 432.0 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 19.74 | 104.3 | 0 | 5 |  |
| 10 | PASS | 19.74 | 42.5 | 0 | 5 |  |
| 100 | PASS | 20.81 | 45.7 | 0 | 5 |  |
| 1000 | PASS | 35.31 | 38.2 | 0 | 5 |  |
| 10000 | PASS | 187.84 | 38.4 | 0 | 5 |  |
| 100000 | PASS | 1723.62 | 41.2 | 0 | 5 |  |

_Peak CPU at level 100000: worker-mains 107.4% (per service: {'celery-scheduler': 2.4, 'worker-periodic': 10.2, 'chris': 10.8, 'worker-mains': 107.4, 'db': 37.0, 'nats': 0.1, 'dragonflydb': 11.1, 'pfcon': 27.1})_

_Peak disk write at level 100000: db 999.0 MiB (per service: {'worker-periodic': '308.0 KiB', 'chris': '740.0 KiB', 'worker-mains': '102.3 MiB', 'db': '999.0 MiB', 'pfcon': '32.0 KiB'})_

_Postgres at level 100000: workload checkpoints 1 done (2 timed / 0 requested), WAL 465.6 MiB (112 full-page images), temp files 0 B, db container wrote 1.2 GiB, of which zero-filling new WAL segments 352.0 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 37.6 MiB (7,938 full-page images), temp files 0 B, db container wrote 67.6 MiB, of which zero-filling new WAL segments 16.0 MiB_

## Environment

| Field | Value |
|---|---|
| Host OS | Ubuntu 26.04.1 LTS |
| Kernel | 7.0.0-38-generic |
| Arch | x86_64 |
| Host CPUs | 16 |
| Host memory (bytes) | 132318363648 |
| Docker root | /var/lib/docker |
| Engine | 29.9.0 |
| API auth | token |
| Noise floor (health p50/p95 ms) | 3.8 / 5.8 |

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

