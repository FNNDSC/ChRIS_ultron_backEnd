# Benchmark Resource Envelope

A breaking point is only reproducible relative to a **fixed, recorded resource envelope**.
`docker-compose.benchmark.yml` pins one and restores a production-like `uvicorn` runtime;
every value below is also written into each run's `environment.json` and `report.md`.

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

The benchmark `db` also preloads `pg_stat_statements` (the harness snapshots top queries
per scenario); this is measurement instrumentation, not part of the SUT envelope.

**Set the knobs consistently across `bench-start` and `bench-run`.** The services read
them when the stack starts; the harness reads them again at run time to *record* them. If
the two invocations use different values, the report's recorded envelope won't match the
running stack. The simplest way to stay consistent is to export them once (or put them in
a shell/env file) before both commands.

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
