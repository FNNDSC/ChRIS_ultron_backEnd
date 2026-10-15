# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-13T233911Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 8ea010b (dirty: false)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 1.4 MiB (68 full-page images), temp files 0 B, db container wrote 26.6 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 7.19 | 96.4 | 0 | 2 |  |
| 2 | PASS | 12.38 | 43.3 | 0 | 3 |  |

_Peak CPU at level 2: dragonflydb 5.9% (per service: {'worker-periodic': 5.7, 'celery-scheduler': 0.0, 'chris': 3.0, 'worker-mains': 0.5, 'nats': 0.0, 'dragonflydb': 5.9, 'db': 3.3, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 68.0 KiB (1 full-page images), temp files 0 B, db container wrote 840.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.3 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.19 | 40.1 | 0 | 2 |  |
| 10 | PASS | 9.27 | 43.6 | 0 | 2 |  |

_Peak CPU at level 10: db 9.2% (per service: {'worker-periodic': 6.4, 'celery-scheduler': 2.0, 'chris': 3.3, 'worker-mains': 5.5, 'nats': 0.0, 'dragonflydb': 7.8, 'db': 9.2, 'pfcon': 0.0})_

_Postgres at level 10: workload checkpoints 0 done (0 timed / 0 requested), WAL 96.0 KiB (4 full-page images), temp files 0 B, db container wrote 16.9 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.0 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.37 | 43.0 | 0 | 3 |  |
| 2 | PASS | 11.4 | 38.2 | 0 | 4 |  |

_Peak CPU at level 2: worker-mains 20.9% (per service: {'worker-periodic': 9.1, 'celery-scheduler': 1.8, 'chris': 3.7, 'worker-mains': 20.9, 'nats': 0.0, 'dragonflydb': 6.8, 'db': 9.0, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 374.6 KiB (29 full-page images), temp files 0 B, db container wrote 1.8 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.34 | 42.3 | 0 | 3 |  |
| 2 | PASS | 11.36 | 37.6 | 0 | 4 |  |

_Peak CPU at level 2: dragonflydb 7.9% (per service: {'worker-periodic': 3.6, 'celery-scheduler': 0.0, 'chris': 3.1, 'worker-mains': 0.3, 'nats': 0.0, 'dragonflydb': 7.9, 'db': 2.5, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 78.3 KiB (0 full-page images), temp files 0 B, db container wrote 816.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.41 | 37.6 | 0 | 3 |  |
| 2 | PASS | 19.81 | 62.4 | 0 | 5 |  |

_Peak CPU at level 2: worker-periodic 9.3% (per service: {'worker-periodic': 9.3, 'celery-scheduler': 1.3, 'chris': 3.8, 'worker-mains': 0.3, 'nats': 0.1, 'dragonflydb': 6.3, 'db': 4.8, 'pfcon': 0.0})_

_Peak disk write at level 2: worker-mains 176.0 KiB (per service: {'worker-periodic': '52.0 KiB', 'chris': '16.0 KiB', 'worker-mains': '176.0 KiB'})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 163.4 KiB (4 full-page images), temp files 0 B, db container wrote 1.2 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.5 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

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
| Noise floor (health p50/p95 ms) | 4.0 / 5.6 |

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

