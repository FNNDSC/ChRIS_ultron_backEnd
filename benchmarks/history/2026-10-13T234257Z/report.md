# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-13T234257Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 8ea010b (dirty: false)

Levels run: 6  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 3 done (7 timed / 0 requested), WAL 626.4 MiB (16,247 full-page images), temp files 217.1 MiB, db container wrote 1.5 GiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 19.79 | 87.7 | 0 | 5 |  |
| 10 | PASS | 19.77 | 44.8 | 0 | 5 |  |
| 100 | PASS | 20.76 | 101.5 | 0 | 5 |  |
| 1000 | PASS | 35.24 | 43.3 | 0 | 5 |  |
| 10000 | PASS | 187.75 | 38.8 | 0 | 5 |  |
| 100000 | PASS | 1718.85 | 39.5 | 0 | 5 |  |

_Peak CPU at level 100000: db 109.4% (per service: {'worker-periodic': 10.3, 'worker-mains': 102.1, 'celery-scheduler': 2.5, 'chris': 7.2, 'db': 109.4, 'nats': 0.1, 'dragonflydb': 10.0, 'pfcon': 43.0})_

_Peak disk write at level 100000: db 1016.0 MiB (per service: {'worker-periodic': '304.0 KiB', 'worker-mains': '78.2 MiB', 'chris': '728.0 KiB', 'db': '1016.0 MiB', 'pfcon': '36.0 KiB'})_

_Postgres at level 100000: workload checkpoints 3 done (5 timed / 0 requested), WAL 470.0 MiB (1,423 full-page images), temp files 158.5 MiB, db container wrote 1.1 GiB; cleanup checkpoints 0 done (1 timed / 0 requested), WAL 79.5 MiB (9,000 full-page images), temp files 58.6 MiB, db container wrote 196.6 MiB_

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
| Noise floor (health p50/p95 ms) | 4.0 / 5.5 |

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
| db | 2.0 | 4.0 GiB | 8.0 GiB | 64.0 MiB |
| dragonflydb | — | — | — | 64.0 MiB |
| nats | — | — | — | 64.0 MiB |
| pfcon | 2.0 | 2.0 GiB | 4.0 GiB | 64.0 MiB |
| worker-mains | 4.0 | 4.0 GiB | 8.0 GiB | 64.0 MiB |
| worker-periodic | — | — | — | 64.0 MiB |

### PostgreSQL (key settings; environment.json has all)

| Setting | Value |
|---|---|
| autovacuum_max_workers | 3 |
| autovacuum_worker_slots | 16 |
| checkpoint_completion_target | 0.9 |
| checkpoint_timeout | 5min |
| config_file | /var/lib/postgresql/18/docker/postgresql.conf |
| data_checksums | on |
| DateStyle | ISO, MDY |
| default_text_search_config | pg_catalog.english |
| dynamic_shared_memory_type | posix |
| effective_cache_size | 4GB |
| effective_io_concurrency | 16 |
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
| log_lock_waits | off |
| log_min_duration_statement | -1 |
| log_timezone | Etc/UTC |
| maintenance_work_mem | 64MB |
| max_connections | 300 |
| max_parallel_workers_per_gather | 2 |
| max_wal_size | 1GB |
| min_wal_size | 80MB |
| random_page_cost | 4 |
| server_version | 18.2 (Debian 18.2-1.pgdg13+1) |
| shared_buffers | 128MB |
| shared_preload_libraries | pg_stat_statements |
| synchronous_commit | on |
| TimeZone | Etc/UTC |
| track_io_timing | off |
| wal_buffers | 4MB |
| wal_compression | off |
| wal_level | replica |
| work_mem | 4MB |

_`core_chrisfile` storage parameters: defaults_

_`core_chrisfolder` storage parameters: defaults_

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

