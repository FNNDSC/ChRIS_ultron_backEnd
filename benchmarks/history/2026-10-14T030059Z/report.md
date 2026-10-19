# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-14T030059Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 2d52608 (dirty: false)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 1 done (3 timed / 0 requested), WAL 5.1 GiB (84,863 full-page images), temp files 1.6 GiB, db container wrote 18.8 GiB, of which zero-filling new WAL segments 4.0 GiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.53 | 90.6 | 0 | 6 |  |
| 2 | PASS | 19.18 | 40.4 | 0 | 11 |  |
| 4 | PASS | 41.03 | 45.0 | 0 | 21 |  |
| 8 | PASS | 2856.42 | 353.0 | 0 | 41 |  |

_Peak CPU at level 8: worker-mains 401.9% (per service: {'chris': 72.7, 'worker-mains': 401.9, 'celery-scheduler': 4.0, 'worker-periodic': 13.7, 'dragonflydb': 8.7, 'nats': 0.3, 'db': 201.3, 'pfcon': 5.8})_

_Peak disk write at level 8: db 17.6 GiB (per service: {'chris': '14.0 MiB', 'worker-mains': '1.9 GiB', 'worker-periodic': '652.0 KiB', 'db': '17.6 GiB', 'pfcon': '260.0 KiB'})_

_Postgres at level 8: workload checkpoints 1 done (3 timed / 0 requested), WAL 4.9 GiB (12,011 full-page images), temp files 1016.4 MiB, db container wrote 17.6 GiB, of which zero-filling new WAL segments 3.8 GiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 193.2 MiB (72,776 full-page images), temp files 626.5 MiB, db container wrote 1.1 GiB, of which zero-filling new WAL segments 192.0 MiB_

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
| Noise floor (health p50/p95 ms) | 4.0 / 7.5 |

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

