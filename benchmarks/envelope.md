# Benchmark Resource Envelope

A breaking point is only reproducible relative to a **fixed, recorded resource envelope**.
`docker-compose.benchmark.yml` pins one and restores a production-like `uvicorn` runtime.
Every value below is also written into each run's `environment.json` and `report.md`: the
CPU and memory limits as each container's limits were actually applied (`limits`), the other
knobs as the environment variables gave them (`envelope`).

The dev defaults deliberately throttle CUBE (single `uvicorn` worker, DB pool `max_size: 2`).
The benchmark instead sets explicit, production-like values via `config/settings/benchmark.py`
and the compose override, so it measures CUBE's *architecture* capacity rather than an
artificial dev cap.

## Knobs (env vars, with defaults)

| Env var | Default | What it sets |
|---|---|---|
| `CUBE_UVICORN_WORKERS` | `4` | `uvicorn --workers` on the `chris` service |
| `CUBE_CPUS` / `CUBE_MEM_LIMIT` | `4` / `4g` | `chris` CPU and memory limits |
| `CUBE_WORKER_MAINS_CONCURRENCY` | `4` | `celery -c` on `worker-mains` (job submission parallelism) |
| `CUBE_WORKER_CPUS` / `CUBE_WORKER_MEM_LIMIT` | `4` / `4g` | `worker-mains` CPU and memory |
| `CUBE_DB_POOL_MIN_SIZE` | `2` | psycopg pool `min_size` (per process) |
| `CUBE_DB_POOL_MAX_SIZE` | `10` | psycopg pool `max_size` (per process) |
| `CUBE_DB_POOL_TIMEOUT` | `10` | psycopg pool acquire timeout (s) |
| `CUBE_DB_MAX_CONNECTIONS` | `300` | Postgres `max_connections` (must cover all process pools) |
| `CUBE_DB_SYNCHRONOUS_COMMIT` | `on` | Postgres `synchronous_commit` (see below) |
| `CUBE_DB_CPUS` / `CUBE_DB_MEM_LIMIT` | `2` / `4g` | `db` CPU and memory |
| `PFCON_WORKERS` | `8` | `gunicorn -w` on `pfcon` (compute-side request parallelism) |
| `PFCON_CPUS` / `PFCON_MEM_LIMIT` | `2` / `2g` | `pfcon` CPU and memory |
| `CUBE_CELERY_POLL_INTERVAL` | `2.0` | Celery-beat scheduling/status poll cadence (s) — sweep `{2, 4, 8}` |
| `CUBE_DEBUG` | `false` | Django `DEBUG` on `chris` and the Celery services (see below) |

**Why `DEBUG` is off:** production runs with `DEBUG = False`, and `DEBUG` changes what is
measured: every SQL statement goes through Django's query recorder, the debug toolbar's
middleware runs on every request, and a 500 renders a page that re-runs the QuerySets of each
stack frame. Runs up to and including 2026-09-17 had it on (it came from
`config.settings.local`), so `bench-compare` reports `envelope.CUBE_DEBUG` as a caution against
them. `CUBE_DEBUG=true` brings that overhead back for a comparison with those runs, but not the
connection leak that broke their Locust steps from 100 users up, which CUBE has fixed since
(REPORT.md § 14).

**Why `synchronous_commit` stays on:** it is PostgreSQL's default, and what a deployment that
cannot lose acknowledged writes runs with: each commit waits until its WAL is flushed to disk.
`CUBE_DB_SYNCHRONOUS_COMMIT=off` exists in the benchmark override only, never on the dev stack.
With it a commit returns before the flush, so a crash can lose up to about three
`wal_writer_delay` periods (600 ms) of transactions their clients saw commit, though it never
corrupts the database. Use it to measure how much of a scenario waits on commit flushes, not
as a baseline: `bench-compare` flags `envelope.CUBE_DB_SYNCHRONOUS_COMMIT` and
`postgres.synchronous_commit` between an `on` and an `off` run.

**Not part of the envelope:** `CUBE_DB_POOL_STATS_INTERVAL` (default `5`) is the number of
seconds between the `db_pool_stats` log lines each `uvicorn` worker writes, which the Locust
recovery check reads (`0` disables them). It is instrumentation and is not recorded.

**Why the 2.0 s floor for the Celery poll interval:** the periodic tasks are guarded by `skip_if_running`
(`plugininstances/tasks.py`), which spends ~1 s in a broker-wide `inspect().active()`
broadcast on every invocation. At a cadence ≤ ~1 s consecutive invocations overlap and
can each see the other as "running" → they *mutually skip* and scheduling stalls
(observed: instances stuck in `waiting` for 44–116 s at `1.0`). Until that guard is
reworked, do not benchmark below `2.0`.

Set any of them inline, e.g.:

```bash
CUBE_UVICORN_WORKERS=8 CUBE_DB_POOL_MAX_SIZE=20 CUBE_DB_MAX_CONNECTIONS=500 \
  just bench-start
```

**Connection budget:** each `uvicorn` worker and each Celery worker process holds its own
pool of up to `CUBE_DB_POOL_MAX_SIZE` connections, so keep
`CUBE_DB_MAX_CONNECTIONS ≥ (uvicorn_workers + celery_processes) × pool_max + headroom`.

`postgres/cube.conf` (below) also preloads `pg_stat_statements` on both stacks (the harness
snapshots every statement per scenario); this is measurement instrumentation, not part of the
SUT envelope.

**Set the knobs consistently across `bench-start` and `bench-run`.** The services read
them when the stack starts; the harness reads them again at run time to *record* them. If
the two invocations use different values, the report's recorded envelope won't match the
running stack. The simplest way to stay consistent is to export them once (or put them in
a shell/env file) before both commands. The container limits and the Postgres settings are
read from the running stack instead, so they cannot drift.

## PostgreSQL configuration

Both compose stacks start `db` with `postgres -c config_file=/etc/postgresql/cube.conf`, the
committed [`postgres/cube.conf`](../postgres/cube.conf); this override only adds
`max_connections` and `synchronous_commit` to that command line. The file replaces the
`postgresql.conf` that initdb wrote into the data directory, so it first restates the image's
own lines (`listen_addresses = '*'`, the locale, the text-search configuration). Then it sets:

| Setting | Value | Why |
|---|---|---|
| `shared_buffers` / `effective_cache_size` | 1GB / 3GB | 25% / 75% of the `db` limit (`CUBE_DB_MEM_LIMIT`, 4 GB); an aged `core_chrisfile` of about 2 M rows is 1 GB with its indexes |
| `work_mem` / `maintenance_work_mem` | 32MB / 512MB | the file-table sorts of a 100k-file output stay in memory; vacuum and index builds on the file table |
| `max_wal_size` / `min_wal_size` / `checkpoint_timeout` / `checkpoint_completion_target` | 8GB / 1GB / 15min / 0.9 | at 1 GB, a deep DAG's registrations forced a checkpoint every few minutes, and after each one every page changed again is written to the WAL in full |
| `wal_compression` | lz4 | compresses those full-page images; lz4 costs far less CPU than pglz (`on`) on a 2-CPU `db` |
| `random_page_cost` / `effective_io_concurrency` | 1.1 / 200 | SSD/NVMe rather than rotating-disk defaults; PostgreSQL 18's `io_max_concurrency` bounds the 200 |
| `timezone` | UTC | Django compares it as a string, and the image's `Etc/UTC` costs a `set_config` on every new connection |
| `shared_preload_libraries`, `track_io_timing`, `log_min_duration_statement`, `log_lock_waits` | pg_stat_statements, on, 1s, on | query attribution, IO timings, and slow statements and lock waits in the `db` log |

On `core_chrisfile` and `core_chrisfolder`, autovacuum runs once 2% of the rows are updated or
deleted, and autoanalyze once 1% are inserted, updated or deleted (PostgreSQL's defaults: 20%
and 10%). Inserts alone still trigger a vacuum at the default 20%
(`autovacuum_vacuum_insert_scale_factor`). Migration `core.0004` sets this, and each run
records it under `table_options`.

What follows from the file:

- **`shm_size: 1g` on `db`.** A parallel hash join keeps its table in `/dev/shm`, up to
  `work_mem` × `hash_mem_multiplier` (2) per process. Docker's 64 MB default fails such joins
  at 32 MB with "could not resize shared memory segment". The tmpfs counts against the
  container's memory as it fills.
- **The sizes do not follow `CUBE_DB_MEM_LIMIT`.** About 1.1 GB of shared memory is
  allocated whatever the limit, so keep the limit well above it. Watch `cgroup_oom_kill` in
  the counters.
- **Slow bulk inserts are logged in full.** Django binds parameters on the client, so a
  registration's `INSERT … UNNEST` reaches the server with every file path inlined, and
  `log_min_duration_statement` logs all of it: 10–15 MB per 100,000 files, more with deeper
  paths. The `db` container's log can grow by hundreds of MB in a deep run until
  registration is batched. Docker writes it outside the container, so `cgroup_write_bytes`
  does not include it.
- **New WAL segments are zero-filled.** PostgreSQL writes zeros into each new 16 MB WAL
  segment before using it. At each checkpoint it keeps old segments for reuse only up to
  about what the recent checkpoints needed (never below `min_wal_size`) and deletes the rest.
  So zero-filling happens whenever the WAL between checkpoints outgrows the pool it kept:
  on a fresh volume, and again after lighter load or a server restart has shrunk the pool.
  At `max_wal_size` 8GB that can be several GB in one heavy run, where the default 1GB
  capped it near 1 GB. The counters record it as `wal_init_bytes`, part of
  `cgroup_write_bytes`. Compare what `db` wrote with and without it, and keep the order of
  runs on a volume the same between the runs you compare.
- **The `db` volume keeps its WAL.** Once written, at least `min_wal_size` (1 GB) of
  segments stays in the volume, and up to about `max_wal_size` after heavy runs. The dev
  and benchmark stacks share the volume, so a laptop keeps it after a benchmark;
  `just nuke` reclaims it.
- **Restart the stack after editing the file** (`just bench-down && just bench-start`),
  not `db` alone. CUBE's connection pools would keep the connections the restart closed,
  each would fail one request with a 500, and the harness counts any 5xx as a hard failure.
  `just bench-start` against a running stack recreates `db` when its configuration changed,
  but not the CUBE services, so bring the stack down first. `shared_buffers`,
  `shared_preload_libraries`, `listen_addresses` and `dynamic_shared_memory_type` change
  only at server start; the others would also follow `SELECT pg_reload_conf()`. The data
  directory's `postgresql.conf` is no longer read. `ALTER SYSTEM` (`postgresql.auto.conf`)
  still overrides the file, and a run records any such override under `altered`.

## What each run records about Postgres

The harness reads these from the running server and the `db` container.

- **Settings** — `environment.json` → `postgres`:
  - `settings` holds every setting's value as `SHOW` prints it. Two runs therefore hold the
    same names, unless the server version or the preloaded libraries differ (a `db` that does
    not preload `pg_stat_statements` lacks its `pg_stat_statements.*` settings).
  - `key_settings` names the ones `report.md` lists: a fixed list (`POSTGRES_SETTINGS` in
    `environment.py`: version and config file, memory, WAL and checkpoints, IO, planner,
    instrumentation) plus every setting a configuration file or the command line sets.
  - `altered` lists the settings in effect from `ALTER SYSTEM`. They win over the
    configuration file and survive restarts in the `db` volume.
  - `table_options` holds the storage parameters of `core_chrisfile` and `core_chrisfolder`.

  The `db` image id is under `images`, and each container's CPU, memory, swap and `/dev/shm`
  limits are under `limits`. `bench-compare` reports a differing setting or limit as a
  caution. A run that predates a block gets a single "not recorded" caution instead. Runs
  from before 2026-10-13 have neither block nor the `CUBE_DB_SYNCHRONOUS_COMMIT` knob, which
  then reads `None` although they ran with PostgreSQL's default, `on`. So a new run gets
  those three cautions against every archived run. Locust steps record the same `postgres`
  block in their `<csv prefix>_recovery.json`.
- **Counters** — snapshots of the server's cumulative counters, plus the `db` container's
  cgroup counters:
  - Server: checkpoints done, timed and requested, WAL bytes and full-page images, the WAL
    writes that only zero-filled new segments (`wal_init_bytes`), temp files,
    sessions, and autovacuum and autoanalyze runs on the two file tables. Also the bytes each
    process type wrote or extended, per object (`pg_stat_io`; keys
    `io_write_bytes:<object>:<process_type>` with spaces as underscores, e.g.
    `io_write_bytes:relation:client_backend`, non-zero ones only). `num_timed` also counts
    the timed checkpoints an idle server skips, so `num_done` is the number written.
  - `db` container: bytes written to disk, pages swapped out and in, OOM kills.

  Each scenario records deltas for two windows. `workload` runs from scenario start to the end
  of the workload, slightly wider than the 2 s samples behind `peak_write_bytes`, so its
  `cgroup_write_bytes` is at least `peak_write_bytes.db`. `cleanup` covers feed deletion and
  quiescence. Both windows go into `scenario.json` (`db_counters`, with the raw snapshots).
  Each `levels.jsonl` row gets each counter's largest value across the level's repeats, so the
  counters of one row can come from different repeats. The run's total, taken 11 s after the
  last level, goes into `summary.json` (`db_counters.run`).

  Backends publish their statistics up to about 10 s after they go idle, so a few seconds of
  short transactions can land in the next window. The run total holds everything published by
  its end. Dirty pages Postgres or the kernel has not written yet are in no window.

  Postgres's counters and the container's reset independently:
  - A crash restart, which an OOM-killed backend causes, zeroes Postgres's statistics. The
    window then reads `"reset": true` instead of Postgres's counters, which are unknown, not
    zero.
  - The container keeps running through a crash, so its counters, OOM kills included, keep
    their delta.
  - A server or container restart invalidates both.
  - When Postgres cannot be read at one end of a window (during crash recovery, say), the
    window reads `"unreadable": true` instead of its counters, and the container's remain.

  `report.md` shows the run total and the last level's windows. `bench-compare` shows the two
  runs' totals side by side under "Postgres over the whole run". It trends any level-row value
  through a dotted `--metric`, e.g. `--metric db_counters.workload.num_requested` or
  `--metric peak_write_bytes.db`. Given explicitly, the trend renders for two runs as well.

## Pinned compute resource (per plugin job)

pfcon applies per-plugin-job container CPU/memory limits from the plugin instance resource
descriptors (defaults), independent of the Compose service limits above. The report records
the Compose envelope; note the plugin-job defaults separately if you change them.

## Pinned workload plugin versions

Runs used `dbg-bigfiles` 1.0.0, `pl-simpledsapp` 2.1.5, and `pl-topologicalcopy` 1.0.13
(provisioned by a local edit to `chrisomatic.yml`, below). The harness resolves each plugin **by name** and uses the
first match (CUBE orders by `-version`), so **install exactly one version of each** — otherwise
it warns and binds to the lexicographically-highest version string, not necessarily the pinned
one. Each run now records the resolved versions (and how many matched) under `workload_plugins` in `environment.json`/`summary.json`; the pin is still what keeps a run reproducible, since the harness resolves by name.

**Reproducing those versions.** The committed `chrisomatic/chrisomatic.yml` registers
`pl-topologicalcopy` by name from the public ChRIS store, and the store now serves 2.0.0 — a no-op
image — under that name, so a stock `just` can bind the harness to a plugin that does no work, and
a run against it reads as a large speed-up rather than a failure. Before provisioning a benchmark
stack, edit `chrisomatic.yml` locally: replace `- name: pl-topologicalcopy` with
`- dock_image: fnndsc/pl-topologicalcopy:1.0.13` (Docker Hub carries the 1.0.x tags; the store's
2.0.0 is not there), or add an empty `public_store:` under `on:` to disable the store lookup
altogether. The second option also needs every `- name:` entry turned into a pinned
`- dock_image:`: without a store, chrisomatic cannot resolve a plugin from its name alone, so
those plugins fail to register and `just bench-start` fails. Keep that edit out of commits — the dev environment is deliberately not pinned to the
benchmark's versions. If another version is already registered, remove it first (or `just nuke`),
then confirm `workload_plugins` in the run's `environment.json` reads `pl-topologicalcopy` 1.0.13,
`pl-simpledsapp` 2.1.5 and `dbg-bigfiles` 1.0.0, each with `"matches": 1`.

## Manual hardware fields

`environment.json` auto-captures host CPU/mem (from `docker info`), image ids, engine
versions, git commit, and a measured noise floor. Fill these in by hand in the report:

- **Storage device type / throughput** — e.g. NVMe SSD, ~3 GB/s.
- **Power / thermal mode** — AC vs battery, performance governor, any thermal throttling.
- **Other significant workloads** — anything else running on the box during the sweep.

## Where to run

Authoritative `full`-tier sweeps run on a **dedicated bare-metal Linux box** (no Docker
Desktop VM layer, so `cpus`/`mem_limit` are honored directly). `smoke`/`default` tiers may
run on a laptop but are **directional only** — document the Docker Desktop VM limits there.
