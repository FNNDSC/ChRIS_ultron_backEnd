# CUBE Load & Scalability Benchmark — Report

**Run:** 2026-10-22T124103Z  •  **Tier:** smoke  •  **Storage:** fslink  •  **Commit:** 0677a9c (dirty: false)

Levels run: 10  •  Breaking points: 0

## Breaking points

_No hard failure reached within the configured caps._

## Postgres over the whole run

_checkpoints 0 done (0 timed / 0 requested), WAL 1.1 MiB (68 full-page images), temp files 0 B, db container wrote 9.9 MiB_

## Approach to failure (per axis)

_CPU% is relative to one host core (100% = one core); judge saturation against each service's `cpus` limit in the envelope, not against 100%._

### linear — depth

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 7.17 | 68.1 | 0 | 2 |  |
| 2 | PASS | 12.37 | 43.1 | 0 | 3 |  |

_Peak CPU at level 2: worker-periodic 5.4% (per service: {'worker-mains': 2.7, 'worker-periodic': 5.4, 'chris': 2.7, 'celery-scheduler': 0.0, 'dragonfly-cache': 2.8, 'db': 2.8, 'dragonflydb': 1.0, 'nats': 0.1, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 58.8 KiB (1 full-page images), temp files 0 B, db container wrote 648.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.3 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### linear — file_count

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 8.21 | 123.5 | 0 | 2 |  |
| 10 | PASS | 8.19 | 44.9 | 0 | 2 |  |

_Peak CPU at level 10: db 8.1% (per service: {'worker-mains': 4.1, 'worker-periodic': 6.2, 'chris': 2.5, 'celery-scheduler': 0.0, 'dragonfly-cache': 0.3, 'db': 8.1, 'dragonflydb': 4.7, 'nats': 0.1})_

_Postgres at level 10: workload checkpoints 0 done (0 timed / 0 requested), WAL 56.3 KiB (4 full-page images), temp files 0 B, db container wrote 808.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### fanout_fanin — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.38 | 45.3 | 0 | 3 |  |
| 2 | PASS | 12.42 | 41.5 | 0 | 4 |  |

_Peak CPU at level 2: db 8.0% (per service: {'worker-mains': 4.7, 'worker-periodic': 5.6, 'chris': 3.4, 'celery-scheduler': 0.0, 'dragonfly-cache': 3.3, 'db': 8.0, 'dragonflydb': 0.7, 'nats': 0.1, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 262.4 KiB (29 full-page images), temp files 0 B, db container wrote 1.7 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### diamond — branches

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 12.33 | 38.5 | 0 | 3 |  |
| 2 | PASS | 10.38 | 39.9 | 0 | 4 |  |

_Peak CPU at level 2: worker-periodic 9.2% (per service: {'worker-mains': 8.7, 'worker-periodic': 9.2, 'chris': 4.3, 'celery-scheduler': 2.0, 'dragonfly-cache': 0.4, 'db': 8.0, 'dragonflydb': 4.1, 'nats': 0.1, 'pfcon': 0.0})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 80.7 KiB (0 full-page images), temp files 0 B, db container wrote 816.0 KiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 1.9 KiB (0 full-page images), temp files 0 B, db container wrote 16.0 KiB_

### diamond — layers

| Level | Verdict | Makespan p50 (s) | Worst p95 (ms) | 5xx | Completed | Criteria |
|---|---|---|---|---|---|---|
| 1 | PASS | 11.37 | 39.2 | 0 | 3 |  |
| 2 | PASS | 19.76 | 41.2 | 0 | 5 |  |

_Peak CPU at level 2: worker-periodic 9.3% (per service: {'worker-mains': 7.9, 'worker-periodic': 9.3, 'chris': 6.3, 'celery-scheduler': 1.4, 'dragonfly-cache': 0.3, 'db': 7.6, 'dragonflydb': 1.0, 'nats': 0.1, 'pfcon': 1.6})_

_Peak disk write at level 2: worker-mains 232.0 KiB (per service: {'worker-mains': '232.0 KiB', 'worker-periodic': '48.0 KiB', 'chris': '8.0 KiB'})_

_Postgres at level 2: workload checkpoints 0 done (0 timed / 0 requested), WAL 127.6 KiB (4 full-page images), temp files 0 B, db container wrote 1.1 MiB; cleanup checkpoints 0 done (0 timed / 0 requested), WAL 2.4 KiB (0 full-page images), temp files 0 B, db container wrote 24.0 KiB_

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
| Noise floor (health p50/p95 ms) | 4.0 / 7.1 |

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

| Role | Plugin | Version | Image | Digest | Installed versions |
|---|---|---|---|---|---|
| fs | dbg-bigfiles | 1.0.0 | fnndsc/dbg-bigfiles@sha256:b956e35ee69c249677489b2bf1815a578c129c478bbdc4bff8c4c75535cd3e7f | sha256:b956e35ee69c | 1 |
| ds | pl-simpledsapp | 2.1.5 | fnndsc/pl-simpledsapp@sha256:c4e8726281d4dff3266bb78ea80dcd9e3732eb02dbde86ce5633da2d960a7207 | sha256:c4e8726281d4 | 1 |
| ts | pl-topologicalcopy | 1.0.13 | fnndsc/pl-topologicalcopy@sha256:35cb5798f9035cbd4f879049498ecd3d1bcf93bb95aa0b5eb3960fc65e47b8ee | sha256:35cb5798f903 | 1 |

Pinned by `benchmarks/chrisomatic/benchmark.yml` (sha256 3ec92f12faaa).

### Manual fields (fill in)

- **storage_device_type_throughput:** TODO
- **power_thermal_mode:** TODO
- **other_significant_workloads:** TODO

