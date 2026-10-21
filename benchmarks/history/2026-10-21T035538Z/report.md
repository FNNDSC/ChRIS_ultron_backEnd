# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-21T035538Z  •  **Tier:** full  •  **Storage:** fslink  •  **Commit:** 0c9223b (dirty: true)

Levels run: 8  •  Breaking points: 1

## Breaking points

| Topology | Axis | Broke at level | Criteria |
|---|---|---|---|
| linear | feeds | 128 | cancelled:inst-1001; cancelled:inst-1137 |

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 40.5 MiB (141 full-page images), temp files 0 B, db container wrote 305.3 MiB, WAL segments zero-filled 48.0 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — feeds

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 20.82 | 66.0 | 0 | 5 |  |
| 2 | PASS | 19.29 | 59.3 | 0 | 10 |  |
| 4 | PASS | 20.43 | 53.6 | 0 | 20 |  |
| 8 | PASS | 19.26 | 103.4 | 0 | 40 |  |
| 16 | PASS | 22.6 | 159.8 | 0 | 80 |  |
| 32 | PASS | 43.27 | 532.3 | 0 | 160 |  |
| 64 | PASS | 108.42 | 859.5 | 0 | 320 |  |
| 128 | FAIL | 326.44 | 1593.2 | 0 | 638 | cancelled:inst-1001; cancelled:inst-1137 |

_Peak CPU at level 128: worker-mains 411.5% (per service: {'worker-mains': 411.5, 'celery-scheduler': 2.7, 'chris': 378.6, 'worker-periodic': 23.0, 'dragonflydb': 7.0, 'db': 178.6, 'pfcon': 39.3, 'dragonfly-cache': 3.4, 'nats': 0.1})_

_Peak disk write at level 128: db 112.2 MiB (per service: {'worker-mains': '23.3 MiB', 'chris': '496.0 KiB', 'worker-periodic': '1.4 MiB', 'db': '112.2 MiB', 'pfcon': '4.6 MiB'})_

_Postgres at level 128: workload checkpoints 0 done (0 timed / 0 requested), WAL 20.0 MiB (24 full-page images), temp files 0 B, db container wrote 143.2 MiB, WAL segments zero-filled 16.0 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 569.3 KiB (0 full-page images), temp files 0 B, db container wrote 2.6 MiB_

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
| Noise floor (health p50/p95 ms) | 3.9 / 7.3 |

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

