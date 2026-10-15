# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-14T022103Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 2d52608 (dirty: false)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 1.1 MiB (70 full-page images), temp files 0 B, db container wrote 10.0 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 7.22 | 101.0 | 0 | 2 |  |
| 2 | PASS | 12.44 | 40.7 | 0 | 3 |  |

_Peak CPU at level 2: db 9.6% (per service: {'worker-mains': 4.8, 'celery-scheduler': 0.0, 'chris': 3.5, 'worker-periodic': 5.9, 'db': 9.6, 'dragonflydb': 7.0, 'nats': 0.0, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 60.1 KiB (1 full-page images), temp files 0 B, db container wrote 680.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.3 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.19 | 79.9 | 0 | 2 |  |
| 10 | PASS | 8.22 | 48.6 | 0 | 2 |  |

_Peak CPU at level 10: db 8.0% (per service: {'worker-mains': 3.8, 'celery-scheduler': 0.0, 'chris': 2.6, 'worker-periodic': 6.0, 'db': 8.0, 'dragonflydb': 7.3, 'nats': 0.0, 'pfcon': 0.0})_

_Postgres at level 10: workload checkpoints 0 done (0 timed / 0 requested), WAL 65.5 KiB (4 full-page images), temp files 0 B, db container wrote 876.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.0 KiB (0 full-page images), temp files 0 B, db container wrote 32.0 KiB_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.36 | 41.3 | 0 | 3 |  |
| 2 | PASS | 12.43 | 41.2 | 0 | 4 |  |

_Peak CPU at level 2: db 11.3% (per service: {'worker-mains': 8.6, 'celery-scheduler': 2.3, 'chris': 3.5, 'worker-periodic': 9.4, 'db': 11.3, 'dragonflydb': 5.6, 'nats': 0.0, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 264.7 KiB (29 full-page images), temp files 0 B, db container wrote 1.7 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.4 | 44.6 | 0 | 3 |  |
| 2 | PASS | 11.38 | 41.4 | 0 | 4 |  |

_Peak CPU at level 2: worker-periodic 9.9% (per service: {'worker-mains': 9.7, 'celery-scheduler': 1.8, 'chris': 3.1, 'worker-periodic': 9.9, 'db': 6.0, 'dragonflydb': 6.8, 'nats': 0.1, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 80.6 KiB (0 full-page images), temp files 0 B, db container wrote 848.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.0 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.33 | 42.0 | 0 | 3 |  |
| 2 | PASS | 19.83 | 43.4 | 0 | 5 |  |

_Peak CPU at level 2: db 10.1% (per service: {'worker-mains': 5.2, 'celery-scheduler': 1.4, 'chris': 3.2, 'worker-periodic': 9.0, 'db': 10.1, 'dragonflydb': 7.1, 'nats': 0.0, 'pfcon': 0.0})_

_Peak disk write at level 2: db 596.0 KiB (per service: {'worker-mains': '212.0 KiB', 'chris': '16.0 KiB', 'worker-periodic': '40.0 KiB', 'db': '596.0 KiB'})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 133.3 KiB (6 full-page images), temp files 0 B, db container wrote 1.2 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.7 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

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
| Noise floor (health p50/p95 ms) | 3.8 / 6.3 |

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

