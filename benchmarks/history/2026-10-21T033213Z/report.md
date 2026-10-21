# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-21T033213Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 0c9223b (dirty: true)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 1.1 MiB (70 full-page images), temp files 0 B, db container wrote 9.7 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.25 | 79.5 | 0 | 2 |  |
| 2 | PASS | 11.32 | 83.7 | 0 | 3 |  |

_Peak CPU at level 2: chris 7.5% (per service: {'chris': 7.5, 'celery-scheduler': 0.0, 'worker-mains': 4.1, 'worker-periodic': 5.8, 'db': 4.4, 'dragonflydb': 4.3, 'dragonfly-cache': 3.6, 'nats': 0.1, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 60.2 KiB (1 full-page images), temp files 0 B, db container wrote 672.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.3 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.24 | 40.3 | 0 | 2 |  |
| 10 | PASS | 8.21 | 43.2 | 0 | 2 |  |

_Peak CPU at level 10: db 8.4% (per service: {'chris': 5.9, 'celery-scheduler': 0.0, 'worker-mains': 5.1, 'worker-periodic': 6.0, 'db': 8.4, 'dragonflydb': 4.6, 'dragonfly-cache': 0.5, 'nats': 0.0})_

_Postgres at level 10: workload checkpoints 0 done (0 timed / 0 requested), WAL 61.1 KiB (4 full-page images), temp files 0 B, db container wrote 856.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.3 | 41.1 | 0 | 3 |  |
| 2 | PASS | 11.4 | 39.7 | 0 | 4 |  |

_Peak CPU at level 2: chris 12.7% (per service: {'chris': 12.7, 'celery-scheduler': 0.0, 'worker-mains': 8.3, 'worker-periodic': 5.3, 'db': 4.8, 'dragonflydb': 1.0, 'dragonfly-cache': 3.6, 'nats': 0.0, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 261.3 KiB (29 full-page images), temp files 0 B, db container wrote 1.7 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.41 | 40.5 | 0 | 3 |  |
| 2 | PASS | 12.43 | 38.2 | 0 | 4 |  |

_Peak CPU at level 2: chris 9.9% (per service: {'chris': 9.9, 'celery-scheduler': 0.0, 'worker-mains': 9.9, 'worker-periodic': 6.3, 'db': 6.2, 'dragonflydb': 0.9, 'dragonfly-cache': 0.4, 'nats': 0.1, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 80.4 KiB (0 full-page images), temp files 0 B, db container wrote 824.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.37 | 39.3 | 0 | 3 |  |
| 2 | PASS | 20.77 | 38.6 | 0 | 5 |  |

_Peak CPU at level 2: db 16.0% (per service: {'chris': 12.9, 'celery-scheduler': 2.6, 'worker-mains': 10.2, 'worker-periodic': 10.3, 'db': 16.0, 'dragonflydb': 3.6, 'dragonfly-cache': 3.7, 'nats': 0.1, 'pfcon': 1.7})_

_Peak disk write at level 2: db 420.0 KiB (per service: {'chris': '20.0 KiB', 'worker-mains': '200.0 KiB', 'worker-periodic': '40.0 KiB', 'db': '420.0 KiB'})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 127.1 KiB (6 full-page images), temp files 0 B, db container wrote 1.2 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.5 KiB (0 full-page images), temp files 0 B, db container wrote 32.0 KiB_

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
| Noise floor (health p50/p95 ms) | 3.7 / 8.3 |

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
| CUBE_CACHE_URL | redis://dragonfly-cache:6379/0 |

### Container limits (as applied)

| Service | CPUs | Memory | Memory + swap | /dev/shm |
|---|---|---|---|---|
| celery-scheduler | 0.5 | 512.0 MiB | 1.0 GiB | 64.0 MiB |
| chris | 4.0 | 4.0 GiB | 8.0 GiB | 64.0 MiB |
| db | 2.0 | 4.0 GiB | 8.0 GiB | 1.0 GiB |
| dragonfly-cache | 1.0 | 512.0 MiB | 1.0 GiB | 64.0 MiB |
| dragonflydb | 2.0 | 1.0 GiB | 2.0 GiB | 64.0 MiB |
| nats | — | — | — | 64.0 MiB |
| pfcon | 2.0 | 2.0 GiB | 4.0 GiB | 64.0 MiB |
| worker-mains | 4.0 | 4.0 GiB | 8.0 GiB | 64.0 MiB |
| worker-periodic | 1.0 | 1.0 GiB | 2.0 GiB | 64.0 MiB |

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

