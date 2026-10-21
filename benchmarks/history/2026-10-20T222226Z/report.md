# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-20T222226Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 5bc2e49 (dirty: true)

Levels run: 8  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 40.2 MiB (146 full-page images), temp files 0 B, db container wrote 302.9 MiB, WAL segments zero-filled 48.0 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 19.73 | 99.0 | 0 | 5 |  |
| 2 | PASS | 20.42 | 73.0 | 0 | 10 |  |
| 4 | PASS | 19.31 | 101.6 | 0 | 20 |  |
| 8 | PASS | 19.32 | 103.4 | 0 | 40 |  |
| 16 | PASS | 47.94 | 233.3 | 0 | 80 |  |
| 32 | PASS | 43.11 | 481.5 | 0 | 160 |  |
| 64 | PASS | 103.34 | 929.9 | 0 | 320 |  |
| 128 | PASS | 308.02 | 1601.5 | 0 | 640 |  |

_Peak CPU at level 128: chris 402.2% (per service: {'chris': 402.2, 'celery-scheduler': 2.7, 'worker-mains': 399.6, 'worker-periodic': 15.4, 'db': 189.6, 'nats': 0.0, 'dragonflydb': 13.4, 'pfcon': 67.5})_

_Peak disk write at level 128: db 110.7 MiB (per service: {'chris': '464.0 KiB', 'worker-mains': '22.7 MiB', 'worker-periodic': '1.6 MiB', 'db': '110.7 MiB', 'pfcon': '4.6 MiB'})_

_Postgres at level 128: workload checkpoints 0 done (0 timed / 0 requested), WAL 20.0 MiB (21 full-page images), temp files 0 B, db container wrote 144.7 MiB, WAL segments zero-filled 16.0 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 579.9 KiB (0 full-page images), temp files 0 B, db container wrote 2.6 MiB_

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
| Noise floor (health p50/p95 ms) | 3.9 / 7.4 |

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

