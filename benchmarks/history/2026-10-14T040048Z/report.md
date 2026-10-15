# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-14T040048Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 8ea010b (dirty: false)

Levels run: 4  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 25 done (7 timed / 21 requested), WAL 11.9 GiB (1,187,817 full-page images), temp files 2.2 GiB, db container wrote 34.2 GiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.5 | 90.1 | 0 | 6 |  |
| 2 | PASS | 19.22 | 101.0 | 0 | 11 |  |
| 4 | PASS | 41.04 | 46.6 | 0 | 21 |  |
| 8 | PASS | 2902.05 | 318.3 | 0 | 41 |  |

_Peak CPU at level 8: worker-mains 406.7% (per service: {'chris': 73.4, 'worker-periodic': 14.5, 'worker-mains': 406.7, 'celery-scheduler': 3.1, 'nats': 0.3, 'dragonflydb': 10.9, 'db': 204.3, 'pfcon': 128.3})_

_Peak disk write at level 8: db 30.1 GiB (per service: {'chris': '1.2 MiB', 'worker-periodic': '636.0 KiB', 'worker-mains': '1.7 GiB', 'db': '30.1 GiB', 'pfcon': '88.7 MiB'})_

_Postgres at level 8: workload checkpoints 22 done (7 timed / 18 requested), WAL 9.8 GiB (916,632 full-page images), temp files 1.4 GiB, db container wrote 30.7 GiB; cleanup checkpoints 3 done (0 timed / 3 requested), WAL 2.1 GiB (271,106 full-page images), temp files 771.8 MiB, db container wrote 3.3 GiB_

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
| Noise floor (health p50/p95 ms) | 3.9 / 5.8 |

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

