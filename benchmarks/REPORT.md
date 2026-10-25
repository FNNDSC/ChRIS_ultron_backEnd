# CUBE Load & Scalability — Findings and Recommendations

**Date:** 2026-06-18  •  **For:** ChRIS_ultron_backEnd maintainers — scalability assessment and architecture roadmap

## 1. Executive Summary

This is a load & scalability assessment of **CUBE** (ChRIS Ultron Backend), run with the repo-native harness under `benchmarks/`: a data-plane DAG (directed acyclic graph) harness that escalates one factor at a time until CUBE breaks, plus a Locust control-plane (RED — rate, errors, duration percentiles) layer. All runs used `fslink` storage on a dedicated 16-core / 128 GB Linux box against a pinned, recorded envelope.

Key findings:

- **Status polling dominates orchestration latency, not real work.** For fast workflows, **~98% of end-to-end makespan is spent waiting for the next Celery-beat poll** (measured via a poll-interval sweep); for long-running jobs it drops to ~5%. This is the largest single architectural lever.
- **The control plane saturates at ~50 concurrent API clients (~117 req/s), and the wall is DB connection-pool exhaustion** — p95 pins at the 10 s pool-acquire timeout, then throughput collapses and 5xx/401 cascades begin.
- **The status-check Celery queue (`main2`) is the data-plane backpressure point** — it floods to hundreds of tasks at every breaking point while the submission queue (`main1`) stays near zero.
- **The database hot path is `core_chrisfile` registration/listing**, with statements reaching **35–66 s** under deep DAGs: an unindexed `fname LIKE` prefix scan, a per-path-component folder-insert storm, and a feed-row `FOR KEY SHARE` lock taken **~2M×** that serializes registration within a feed.
- **The layered-diamond topology is a scalability cliff** — makespan blows up super-linearly (42 s → ~3,400 s from 4 → 8 layers) with a **41–47 GiB** DB write, reproducible on a clean stack.
- **CUBE is robust to state aging** to ~1.9M file rows (feed-execution and create latency stay flat; list latency steps up once, then plateaus), and under `fslink` **file size is irrelevant** — file *count* is the stressor.

§1.1 lists the recommendations these findings drive; §2–§9 give the methodology and the root-cause analysis behind each.

**Corrections (2026-09-16).** Re-reading the raw run artifacts changed the attribution of the linear · depth and concurrent-feeds walls and four claims in §8.2; see §12. The issue set derived from this report uses the corrected attributions.

**Post-upgrade baseline (2026-09-17).** Every analysis the issue set cites was re-run after the upgrade to Django 6.0 and DRF 3.18, and §13 records what reproduced, what moved, and eight further corrections to §3, §4, §5 and §8.

**PostgreSQL configuration (2026-10-14).** Both compose stacks now run `db` on a committed `postgres/cube.conf` sized for the benchmark's 4 GiB `db`. On the layered diamond it removes every size-triggered checkpoint and cuts what `db` writes by 40%. §15 has the before and after runs; the after runs are the baselines from here on.

**Shared cache, Dragonfly v2.0.2 and their envelope (2026-10-21).** CUBE has a shared cache on a Dragonfly of its own, both Dragonflies run v2.0.2, and the benchmark pins their CPUs and memory and those of the periodic worker and beat. A/B runs of the Dragonfly version and of the new limits move no makespan beyond run-to-run variation; §16 has them, and the runs with the limits are the baselines from here on.

### 1.1 Recommendations

Grouped by implementation cost; each cites the section with the supporting measurement and analysis.

**Quick wins — config/envelope, no architecture change**

- **Raise `worker-mains` concurrency and `db` CPUs.** At the feeds and layers walls `worker-mains` leads (219–406%, up to its 4-core limit) with `db` second; both are the levers that move those walls up (§3, §9).
- **Enlarge the DB connection budget.** The control-plane knee is pool exhaustion at ~40 connections; raise `CUBE_DB_POOL_MAX_SIZE` and `CUBE_DB_MAX_CONNECTIONS` (with `db` CPUs to back them) to push the ~50-user / 117-RPS (requests per second) ceiling (§4).
- **Index the filename prefix search.** A `text_pattern_ops` (or `varchar_pattern_ops`) index on `core_chrisfile.fname`, or rewriting the lookup to use the indexed `parent_folder_id` FK (foreign key) instead of `fname LIKE` (§8.2).
- **Keep authenticating once via token** — not per-request Basic auth; `auth-token` runs the password hasher at ~700 ms–1.7 s (§4).

**Architectural**

- **Replace status polling with event-driven status streaming from the compute cluster.** The primary change: `pfcon` pushes status (and log) transitions to CUBE instead of CUBE polling on a beat. Measured impact (§5, §8.1): **~10× makespan reduction for short/interactive workflows**, near-elimination of the `main2` flood, and removal of the poll interval as a scaling constraint. Long compute jobs gain only ~5%, so it is a latency/throughput win for interactive use and a stability win under concurrency.
- **Make registration concurrency-safe without serializing on the feed row.** The per-file-insert `FOR KEY SHARE` lock serializes intra-feed registration; restructure so concurrent instances in the same feed register in parallel (§8.2).
- **Bound the `pl-topologicalcopy` merge cost.** Stop re-reading and re-registering accumulated parent output at every layer, so layered-diamond cost grows linearly, not quadratically (§3.2).
- **Isolate failures between feeds** so one failed or timed-out feed cannot degrade the next (§9).

**Database**

- **Index the `core_chrisfile` hot path** — the `fname` prefix search above, plus verifying indexes cover the registration/listing `WHERE`/`JOIN` columns (`parent_folder_id`, `fname`) (§8.2).
- **Stop rewriting the whole `raw`/`summary` JSONB on every status update** — store large per-instance output metadata out-of-row or update incrementally; the 44 s/call UPDATE feeds the diamond-layers cliff (§8.2).
- **Batch and bound file/folder registration** — 233k `core_chrisfolder` inserts in one scenario points to a folder-model and batch-size review (§8.2).
- **Tune Postgres for the write-heavy registration path** — `db` reached 200%+ CPU and tens of GiB of WAL (write-ahead log) under deep DAGs; review WAL/checkpoint settings and `db` resourcing (§3.2, §8.2). The settings are done for the compose stacks (§15); `db` still saturates its 2 CPUs at 8 layers, and its resources are unchanged.

## 2. Test Environment & Methodology

### 2.1 Hardware and envelope

**Host:** dedicated bare-metal, Ubuntu 26.04 LTS, 16 logical CPUs, 128 GB RAM, Docker 27.3, NVMe storage. Running on metal (no Docker Desktop VM) so Compose `cpus`/`mem_limit` are honored.

The pinned, recorded envelope (production-like `uvicorn`, not the dev `runserver`):

| **Knob** | **Value** |
|---|---|
| `CUBE_UVICORN_WORKERS` | 4 |
| `CUBE_WORKER_MAINS_CONCURRENCY` (`celery -c`) | 4 |
| `PFCON_WORKERS` (`gunicorn -w`) | 8 |
| `CUBE_DB_POOL_MAX_SIZE` (per process) | 10 |
| `CUBE_DB_MAX_CONNECTIONS` | 300 |
| `db` CPUs / `chris` CPUs | 2 / 4 |
| `CUBE_CELERY_POLL_INTERVAL` | 2.0 s (swept 2/4/8) |
| `STORAGE_ENV` | `fslink` |

### 2.2 Two measurement surfaces

- **Data / orchestration plane** — a custom Python harness drives real plugin-instance DAGs (`dbg-bigfiles` → `pl-simpledsapp` → `pl-topologicalcopy`) end-to-end, measuring makespan, per-phase timing, USE (utilization, saturation, errors) resource samples, Celery queue depths, and per-scenario `pg_stat_statements`. It escalates one axis at a time (OFAT — one factor at a time) in binary steps — file count by decades — until a hard failure marks the breaking point.
- **Control plane** — a Locust layer (`locustfile.py`, reusing the `chris_api` Collection+JSON seam) drives concurrent API clients and reports RED.

### 2.3 Scope and validity

- **`fslink` only.** Inter-plugin "copy" is symlink + DB registration, so file **count** stresses the control plane while file **size** does not (confirmed, §7). Byte-copy / object-storage scaling is out of scope.
- **Isolation matters.** Several spurious failures early on were traced to running a scenario on a stack not yet recovered from a prior failure (e.g. a post-timeout cascade). All headline breaking points below were **confirmed on a clean stack**.

## 3. Concurrency & Breaking Points (data plane)

Each axis was escalated until a hard failure (any `finishedWithError`/`cancelled`, 5xx, timeout, or no-progress). Envelope as in §2.1, `CUBE_CELERY_POLL_INTERVAL=2`.

| **Topology · axis** | **Last PASS** | **Breaks at** | **Dominant resource at the wall** |
|---|---|---|---|
| linear · depth | 32 | **64** | `chris` 77%; cancellations + no-progress |
| linear · concurrent feeds | 32 | **64** | `worker-mains` 292%, `db` 107%, p95 991 ms |
| linear · file_count | 10,000 | not reached | `worker-mains` 103%, `db` 147 MiB write |
| fanout_fanin · branches | 64 | not reached | — |
| fanout_fanin · concurrent feeds | 8 | **16** | `worker-mains` 386%, `db` 72% |
| fanout_fanin · file_count | 10,000 | not reached | `worker-mains` 403%, `db` 204 MiB write |
| fanout_fanin · merges | 8 | not reached | trivial (`db` 16%) |
| diamond · branches | 32 | not reached | `db` 106% |
| diamond · layers | 4 | **16** (timeout) | see §3.2 — the cliff |
| diamond · concurrent feeds | 8 | **16** | `worker-mains`, `db` |

### 3.1 Concurrent-feeds capacity

A plain chain (`linear`) sustains **32 concurrent feeds** and breaks at 64. Both **fan-in** topologies break at half that or less (`fanout_fanin` and `diamond` feeds both wall at **16**) — the `ts` merge's "wait for all parents" dependency plus simultaneous branch submission costs more per feed. At every feeds wall the leading resource is `worker-mains` CPU (219–386%, up to its 4-core limit at the fanout wall) with `db` second — and at the diamond-feeds wall `db` (174%) nearly co-limits it (219%).

**Note:** `merges` is cheap — escalating the number of parallel merge instances 1→8 stayed all-PASS at trivial CPU, so the *merge count* is not a bottleneck; branches, feeds, and layers are.

### 3.2 The layered-diamond cliff

Repeated split/merge waves (`diamond · layers`) are pathological:

| **Layers** | **Makespan** | **Verdict** |
|---|---|---|
| 1 | 11.8 s | PASS |
| 2 | 19.9 s | PASS |
| 4 | 41.1 s | PASS |
| 8 | **3,363 s (~56 min)** | DEGRADED |
| 16 | timeout (>3,600 s), **~41 GiB `db` write** | **FAIL** |

Makespan explodes **super-linearly** (42 s → 3,363 s from 4 → 8 layers) and layer 16 drives a **41–47 GiB** Postgres write. Root cause in §8.2: the merge re-registers output that accumulates across layers, so the `core_chrisfile` work grows roughly quadratically with layer depth.

**Note (run provenance):** the makespan/verdict column blends two runs — the figures (3,363 s, ~41 GiB) are from the clean isolated re-run (`192652Z`), which classified layer 8 **PASS** (API p95 stayed under the 2 s SLO — service-level objective — on a quiet stack); the **DEGRADED** label is from the full sweep (`022252Z`, 3,458 s, p95 breached mid-sweep). The makespan blowup reproduces either way — that's the point of the re-run.

### 3.3 Long-running jobs scale *better* on the control plane

Re-running the feeds axes with `pl-simpledsapp --sleepLength 60` (long-active jobs) instead of instant jobs:

| **Topology · feeds** | **Instant jobs** | **60 s jobs** |
|---|---|---|
| linear | breaks at 64 | breaks at 64 |
| fanout_fanin | breaks at 16 | **breaks at 32** |

Long jobs spend their time *sleeping in compute containers* rather than hammering CUBE's control plane, so the concurrency wall holds or moves up. CUBE handles realistic long-running workloads more gracefully than the synthetic instant-job stress.

## 4. Control-Plane Behavior (RED)

Locust read-only saturation sweep, standard envelope:

| **Users** | **RPS** | **Fail %** | **p50** | **p95** | **p99** |
|---|---|---|---|---|---|
| 25 | 67 | 0% | 22 ms | 61 ms | 190 ms |
| **50** | **117** | 2.2% | 32 ms | 110 ms | 520 ms |
| 100 | 49 | 20.6% | 39 ms | **10,000 ms** | 17,000 ms |
| 200 | 81 | 16.9% | 580 ms | 11,000 ms | 14,000 ms |
| 400 | 41 | 66.4% | 8,000 ms | 22,000 ms | 61,000 ms |

**The knee is ~50 concurrent clients / ~117 RPS, and the wall is DB connection-pool exhaustion.** Beyond the knee, throughput *collapses* (117 → 49 RPS) while p95 pins at **exactly 10,000 ms** — the value of `CUBE_DB_POOL_TIMEOUT`. Requests block on psycopg pool acquisition and time out; failures are a 500 cascade, and `auth-token` itself begins 500-ing (cascading to 401s). The pool budget (10/process × 4 `uvicorn` = 40 connections) against 2 `db` CPUs is the constraint.

A clean write-path run (10 users, healthy stack, 0 failures) shows the write path is cheap and `auth-token` is the slowest endpoint:

| **Endpoint** | **p50** | **p95** |
|---|---|---|
| create-instance | 62 ms | 140 ms |
| list-feeds / list-instances | 51 / 72 ms | 110 / 150 ms |
| **auth-token** | **700 ms** | **1,700 ms** |

**Note:** `auth-token` is slow by design (password hasher). This independently validates the harness's "authenticate once, reuse a token" approach — per-request Basic auth would add ~1 s to *every* call.

## 5. Latency: the Polling Bottleneck

The plugin-instance lifecycle is advanced by Celery-beat tasks firing every `CUBE_CELERY_POLL_INTERVAL`. Sweeping that interval over {2, 4, 8} s on a `linear · depth` chain isolates the poller's share of makespan.

**Instant jobs (`sleepLength=0`):**

| **Depth** | **poll=2** | **poll=4** | **poll=8** | **poll8 / poll2** |
|---|---|---|---|---|
| 8 | 36.1 s | 69.5 s | 142.5 s | **3.94×** |

**Long jobs (`sleepLength=60`):**

| **Depth** | **poll=2** | **poll=4** | **poll=8** | **poll8 / poll2** |
|---|---|---|---|---|
| 8 | 516.9 s | 550.1 s | 591.2 s | **1.14×** |

Fitting `makespan = work + k · poll` at depth 8:

- **Instant jobs: work ≈ 0.7 s, i.e. ~98% of makespan is poll-wait.** Makespan tracks the poll interval almost perfectly.
- **60 s jobs: work ≈ 492 s, i.e. only ~5% is poll-wait.**

**Implication:** moving from polling to **event-driven status** would cut makespan by roughly **an order of magnitude for short / interactive workflows** and only marginally (~5%) for long compute jobs. This scopes the event-driven recommendation in §1.1.

## 6. State Aging

CUBE accumulates feeds/files over years. Repeated grow→probe cycles (a fixed 2-instance probe measured against a growing DB) took the file table from ~200 to **~1.9M rows**:

| **files_total** | **makespan p50** | **list p95** | **create p95** |
|---|---|---|---|
| 201 | 9.4 s | 215 ms* | 175 ms* |
| 56,201 | 9.4 s | 440 ms | 68 ms |
| 224,201 | 8.3 s | 432 ms | 55 ms |
| 1,344,201 | 9.4 s | 490 ms | 65 ms |
| 1,904,201 | 8.4 s | 487 ms | 70 ms |

*The 201-row baseline ran cold right after a restart; its high p95/create are warm-up artifacts.*

**CUBE shows no material aging degradation to ~1.9M files.** Feed-execution makespan and create latency are flat; list/query latency takes a one-time step from empty → populated, then **plateaus** (~440–490 ms across a 34× row increase). Registration throughput also held (heavy grows stayed ~155 s/feed past 1M files).

**Caveat:** this grows the *file* table specifically (the largest, and the one the probe's `count` queries hit). A `count()`/index knee at much larger scale (10M+) is not ruled out.

## 7. Storage / File-Size Sanity

Same `linear · depth` curve at 1 KiB vs 1 MiB files (a 1024× increase in bytes):

| **Depth** | **1 KiB** | **1 MiB** | **registered bytes (1 KiB → 1 MiB)** |
|---|---|---|---|
| 8 | 35.2 s | 36.3 s | 92 KB → 94 MB |

Makespan is **identical within noise** despite 1024× the bytes. Under `fslink`, file *size* does not touch the control plane — confirming the design decision to weight file **count** and treat size as a sanity check. Meaningful byte-copy scaling requires a non-`fslink` storage mode (future work).

## 8. Bottleneck Attribution

### 8.1 Queue backpressure — `main2` floods, `main1` does not

Peak Celery queue depths at the breaking points:

| **Scenario** | **main1 (submit)** | **main2 (status)** | **periodic** |
|---|---|---|---|
| linear feeds 64 (FAIL) | 0 | **576** | 0 |
| fanout feeds 16 (FAIL) | 0 | **306** | 0 |
| diamond layers 16 (FAIL) | 0 | **234** | 0 |

Across the entire sweep, peak `main1` was **12** and peak `main2` was **2,249**. The system breaks because **status-check tasks (`check_running_plugin_instances_exec_status`) are produced faster than the 4 worker slots consume them** — never because submission backs up. This is the data-plane signature of the polling problem (§5) and the most direct argument for event-driven status.

### 8.2 Database hot path — `core_chrisfile` registration & listing

Top `pg_stat_statements` entries (by total exec time) in the pathological scenarios:

| **Statement** | **Mean / call** | **Where** |
|---|---|---|
| `SELECT core_chrisfile.* …` | **35 s** | diamond layers 16 (68 calls = 2,371 s) |
| `UPDATE plugininstance SET summary=$1::jsonb, raw=$2 …` | **44 s** | diamond layers 8 (45 calls = 1,984 s) |
| `INSERT INTO core_chrisfile … UNNEST(...)` (bulk register) | 18–66 s | deep layers / high file_count |
| `SELECT COUNT(*) … WHERE fname::text LIKE $1` | 794 ms (×315) | listing (diamond layers 16) |
| `INSERT INTO core_chrisfolder …` | 0.2 ms × **233,123** | per-path-component folders |
| `SELECT … feeds_feed … FOR KEY SHARE OF x` | 0.0 ms × **1,981,408** | feed-row lock per file insert |

Four distinct problems are visible:

1. **Unbounded `core_chrisfile` SELECT/INSERT at deep DAGs** — the merge re-reads and re-registers output that accumulates across layers, so per-call cost reaches tens of seconds. This is the diamond-layers cliff (§3.2).
2. **`fname::text LIKE $1` prefix scans** — the `::text` cast + `LIKE` pattern likely defeats normal indexing; this is the list/aging cost.
3. **A `core_chrisfolder` row per path component** — 233k folder inserts in one scenario is heavy churn.
4. **`FOR KEY SHARE` on the feed row for every file insert** — taken ~2M× in the layers-16 cliff; cheap individually but it **serializes file registration within a feed** under concurrency.

## 9. Architecture Issues

1. **Poll-based scheduling dominates latency.** Beat polling makes makespan a function of the poll interval (~98% poll-wait for fast jobs, §5) and floods `main2` (§8.1). It is the root cause of both the orchestration latency and the data-plane breaking points.
2. **DB connection-pool exhaustion is the control-plane ceiling** (§4) — ~50 concurrent clients saturate the 40-connection budget against 2 `db` CPUs.
3. **The `core_chrisfile` registration path does not scale** — unbounded SELECT/INSERT under deep DAGs, unindexed prefix scans, folder-per-component churn, and per-file feed-row locking (§8.2).
4. **Plugin-instance `raw`/`summary` JSONB is rewritten wholesale** on status updates — O(output size) per update, reaching 44 s/call at depth (§8.2).
5. **The layered-diamond merge accumulates data quadratically** with layer count (§3.2).
6. **No isolation/recovery between failures** — a timed-out scenario left the stack degraded enough to fail the *next* one spuriously, until services were restarted.
7. **Async deletion of large feeds is slow** — multi-minute cleanup/quiesce of the deep-diamond feeds.
8. **`worker-mains` (`-c 4`) and `db` (2 CPUs) are the compute bottlenecks at the feeds and layers walls** — the linear-depth wall instead fails on cancellations/no-progress with `chris` CPU highest (§3).

## 10. Limitations & Future Work

- **`fslink` only** — byte-copy and object-storage (`swift`/`s3`) scaling, and meaningful file-size scaling, are not covered (§7).
- **Single envelope** — bottlenecks were identified but not yet confirmed by sweeping the levers (e.g. `worker-mains -c`, `db` CPUs, pool size); a confirmation sweep would quantify each fix's headroom.
- **Aging to ~1.9M files** — robust in range, but a `count()`/index knee at 10M+ rows is untested (§6).
- **No fault-injection** — error handling was characterized from observed failures (cancellations, pool timeouts, contamination cascades) rather than injected faults (worker kill, DB failover, `pfcon` outage).

## 11. Sources & Reproduction

**Harness & data.** All measurements come from `benchmarks/` (data-plane harness + `locustfile.py`); raw per-run artifacts are under `benchmarks/results/` (gitignored, uncommitted) — `report.md`, `levels.jsonl`, `scenarios/*/pg_stats.json`, `queue_depths.jsonl`, and Locust CSVs under `results/locust/`. The committed milestone subset — with the exact per-run commands, the clean-stack discipline, and the run-ID → finding map — is under [`benchmarks/history/`](history/README.md).

**Reproduce.** Environment and the pinned envelope are in §2.1 ([envelope.md](envelope.md) documents each knob). The core reproduction is two commands against the pinned `fslink` stack; the poll-interval sweep (§5), aging loop (§6), file-size sanity (§7), control-plane RED sweep (§4, `just bench-locust`), and the isolated clean-stack re-runs (§3.2 cliff, §3.3 long jobs) each take their own invocation, listed verbatim in `history/README.md`. Workload plugins were pinned to `dbg-bigfiles` 1.0.0, `pl-simpledsapp` 2.1.5, and `pl-topologicalcopy` 1.0.13; `just bench-start` now registers them from the committed pin, and the harness refuses to start unless the stack holds exactly one version of each, the pinned one ([STRATEGY.md](STRATEGY.md) § Workload Plugins).

```bash
just bench-start              # pinned uvicorn envelope + fslink + workload plugins
just bench-run --tier full    # authoritative OFAT sweep (§3 breaking points, §8 attribution)
```

Every headline figure traces to an archived run (`benchmarks/history/<run_id>/`; re-render with `just bench-report <run_id>`):

| Finding | Archived run(s) |
|---|---|
| §3 breaking points, §8 attribution | `022252Z` (full sweep) |
| §3.1 diamond-feeds wall | `153019Z` (isolated) |
| §3.2 layered-diamond cliff | `192652Z` (clean) + `022252Z` (sweep) |
| §3.3 long-running jobs | `155156Z` (linear), `162609Z` (fanout) |
| §4 control-plane RED | `history/locust/` CSVs |
| §5 poll-interval sweep | `224601/224933/225520Z` (instant), `234231/235952Z` + `001826Z` 06-17 (long) |
| §6 state aging | `165243Z` … `190409Z` |
| §7 file-size sanity | `230851Z` (1 KiB), `231046Z` (1 MiB) |

**Design references:** [STRATEGY.md](STRATEGY.md) (benchmark design rationale), [README.md](README.md) (usage), [envelope.md](envelope.md) (pinned envelope).

## 12. Corrections (2026-09-16)

Re-reading the raw per-scenario artifacts (`pg_stats.json`, `status_samples.jsonl`, `api_requests.jsonl`, the captured service logs) and probing the live schema changed the following. The text above is left as written; the issues derived from this report use these attributions.

- **§3, §9.1: the linear · depth wall (64) is not a load wall.** The scenario logged an HTTP 500 on instance creation, `DataError: value too long for type character varying(1024)`: `ChrisFolder.path` and `ChrisFile.fname` are `varchar(1024)` and each hop adds a `/<plugin>_<id>` path component. The cancellation of `ds40` and the cascade to its descendants are a registration that overflowed the same limit inside a bare `except Exception`, with no log line and no error code.
- **§3.1, §8.1, §9.1: the concurrent-feeds walls are duplicate job submissions, not pfcon or worker capacity.** The captured `pfcon` logs of the diamond · feeds failures (runs 022252Z and 153019Z) show `409 Conflict: The container name "/chris-jid-NNNN" is already in use`. The copy job's `finishedSuccessfully` handler moves the instance to `scheduled` with a plain `save()` and submits the app job with no compare-and-swap, so two overlapping status checks (the `main2` flood) both submit and the loser cancels the instance with `CODE01`. In linear · feeds = 64 all 64 roots and all 64 `ds0` instances ended `finishedSuccessfully`, yet `ds1`–`ds3` of two feeds were cancelled from `waiting`: their `ds0` parent was cancelled by one task and written back by another task's stale in-memory object. The `main2` flood is still the trigger, but the damage goes through non-idempotent handlers, which event-driven status alone would not fix.
- **§1.1, §8.2: the `fname` prefix index already exists.** Django creates a `varchar_pattern_ops` index (`core_chrisfile_fname_<hash>_like`) for the unique field, and the Django-escaped `startswith` queries use it (a 100k-row prefix count takes 41 ms on 2 M rows). The slow `COUNT(*) ... LIKE 'home/%'` is the `userfiles/` pagination counting the whole tree, and ordered pages are slow because a locale-collated b-tree cannot be range-restricted by a prefix; the fix is a code-point collation and cheaper counts, not another index.
- **§1.1, §8.2: `FOR KEY SHARE` does not serialize registration.** The ~2 M statements are PostgreSQL's per-row foreign-key checks on the inserted file and folder rows (`pg_stat_statements` mislabels the table); they cost 23 s of the 3,363 s run, and the lock is shared.
- **§1.1, §8.2, §9.4: the 44 s `UPDATE ... SET summary, raw` is not the per-poll status write.** It is the remote-cleanup write (`WHERE remote_cleanup_status = ...`), executed 44 times and blocked behind the single-transaction cascade deletion of the scenario's feed. The per-poll status write costs 0.2 ms.
- **§3.2, §9.5: the layered-diamond growth is geometric by construction.** Each merge collects all branches and each branch copies its input, so files multiply by `branches` per layer (1,747,610 files at 8 layers). No implementation makes it linear in layers; what CUBE controls is the cost per merged object and the number of passes over the data, and the pre-submission `get_previous_output_path` scan (13–32 s per call, up to 64% of the timed-out run) is the largest of those.

## 13. Post-upgrade baseline (2026-09-17)

The analyses above were re-run on commit 30fbbaf (Django 6.0.8, DRF 3.18.1, Celery 5.6.3, psycopg 3.3.5, PostgreSQL 18.2) on the same box and the same pinned envelope, one run per benchmark command the issue set uses. The runs are archived under [`history/`](history/README.md) as `2026-09-17T*` and the Locust CSVs under `history/locust_2026-09-17/`. Environment differences from June: Docker 27.3 → 29.8 and kernel 7.0.0-22 → 7.0.0-31; `pl-topologicalcopy` was held at 1.0.13 for these runs by a local, uncommitted edit to `chrisomatic/chrisomatic.yml`, because the ChRIS store now serves 2.0.0 (a no-op image) under the same name and `bench-compare` did not check workload plugin versions; the committed pin that has since replaced that edit is described in [envelope.md](envelope.md) § "Pinned workload plugin versions". A side script next to the harness kept each service's full log, `pg_stat_statements` with full query text, `pg_stat_activity` wait events, checkpointer/WAL counters and new-session counts; the numbers below that the harness does not record come from it. Those side artifacts stay on the benchmark box under `benchmarks/results/_campaign/` (gitignored, about 1 GB) and are deliberately not committed.

**Reproduced.** The poll sweep (depth 8: 35.6 / 69.9 / 142.1 s at 2 / 4 / 8 s, June 36.1 / 69.5 / 142.5; with 60 s jobs 516 / 550 / 587 s). The linear · depth wall at 64, same instance, same `DataError: value too long for type character varying(1024)`, same silent cancellation. The layered-diamond cliff (11.8 / 19.9 / 41.5 s at 1 / 2 / 4 layers, 3,260 s at 8, timeout at 16 with 41.9 GB written by `db`; the full sweep's three repeats at 8 layers: 3,364–3,419 s). Registration of a 10,000-file instance: 32.4 s. Remote-cleanup writes blocked behind the feed-deletion transaction (46 calls, 43.6 s mean, longest lock wait 727 s). State aging: probe makespan and create latency flat to 1.85 M files. The control-plane knee on a nearly empty database (~50 users).

**Changed.** With three repeats per level the concurrent-feeds walls came out at linear 128, fanout_fanin 32 and diamond 32, and the full sweep put them at 64, 64 and 32 (June: 64, 16, 16). The walls move because they are a race: pfcon logged duplicate-submission `409`s at every level from 16 feeds up, in runs that passed as well as in runs that failed. A single feed with 64 branches of 1,000 files cancels its merge in every run, which is the reliable reproducer. In the aging series `list p95` grew with the file table (42 ms at 56k files, 385 ms at 1.85 M) instead of stepping once and plateauing. On a database with 1.85 M files the read-only Locust sweep is saturated at 25 users (6 RPS, `userfiles/` 8.9 s p50).

**Corrections this baseline adds.**

- **§5: the poll-wait share is 75 / 88 / 94% at 2 / 4 / 8 s, not ~98%.** Measured per job from submit time, Docker's `FinishedAt` and CUBE's detection time: at 2 s the depth-8 chain spends 26.7 s waiting on polls, 7.4 s running containers and 1.2 s in CUBE. The "~98%" came from a straight-line fit through three makespans. Only two of the three transitions per hop scale with the interval; the scheduling wait stays near 0.9 s because `schedule_waiting_plugin_instances` runs on the same tick and its `inspect().active()` broadcast takes ~1 s.
- **§8.2: most of registration is a redundant listing loop.** `check_files_from_json_exist` lists the whole output tree 60 times on every successful registration, because the retry loop has no `break` once the files are present. Per instance the loop takes 27–34 s at 10,000 files and 267–342 s at 100,000, against 1.8–2.4 s and 19–25 s for everything after it (the sanitize walk, the per-file log line, the insert and the per-file `stat`), so it is 92–94% of each instance's `registeringFiles`, which averaged 32.4 s and 325 s in the targeted runs; in the last layer of diamond · layers = 8 it takes 1,193–1,202 s per branch. Registration is already linear in file count (3.2 ms per file at 10k and at 100k).
- **§8.2: the pre-submission scan runs twice per `ds` child**, once in the copy job and once in the app job (64 calls for 32 `ds` instances at layers 8, 1,008 s total; 2,357 s and 65% of the timed-out layers-16 run). Its `ORDER BY` costs 1,416 ms for 100k rows against 55 ms without it, and 1,402 ms with `work_mem` at 32 MB, so the cost is locale-aware comparison rather than the disk spill. On a synthetic 2 M-row table the ordered query took 2,097 ms with `en_US.utf8` and 65 ms with `pg_c_utf8`, both spilling the same 11 MB.
- **§8.2: the 148 file/folder `SELECT`s that return a whole feed are Django's deletion collector**, not registration.
- **§8.1: the worker log volume is the per-file registration line.** Of the 1.06 GB `worker-mains` wrote in diamond · layers = 8, 1,051 MB is `Registering file -->…` and 4.9 MB the pfcon response bodies. The benchmark settings also write the same lines to an unrotated `/tmp/debug.log` inside the container (916 MB in that scenario, 4.18 GB over the full sweep).
- **§4: `SELECT set_config` is Django's TimeZone, and the Celery workers reconnect per task.** The server default is `Etc/UTC`, Django wants `UTC`, so it sets it on every new connection; Celery's Django fixup closes the whole connection pool before and after every task in a prefork worker, so workers open 100–180 new sessions per second at the feeds walls (about 5 per second in a single-feed run).
- **§4: past the knee the API does not recover.** After a 100-user or 400-user read sweep, with no load, every request failed with a 500 after 10 s for at least three minutes while all 40 pooled connections sat idle on the server, until `chris` was restarted; 25 and 50 users left it healthy. June's sweep did not behave this way: its 200-user step, run right after the 100-user step, still served most requests, while September's served none that needed the database. The September results above 100 users therefore describe a broken stack, and the change may have come with the upgrade. Each sweep also begins with a login storm: `auth-token` takes 0.55 s alone, 1.6 s with 8 concurrent calls and 9 s with 16.
- **§3: a transient compute failure cancels instances; a pause does not.** Restarting pfcon (about 2 s) during a 16-feed fanout run cancelled 24 of 96 instances and stopping it for 30 s cancelled 30, because the copy job's three retries run back to back with no wait, and the app job's submission has no retry at all: it cancels with `CODE01` on the first failed request to pfcon. Pausing pfcon for 60 s cancelled nothing.
- **Envelope notes.** `CELERYD_PREFETCH_MULTIPLIER = 2` has no effect (Celery reads settings with the `CELERY` namespace), so `worker-mains` prefetches 16; `max_wal_size` at 1 GB forced 17 size-triggered checkpoints in the 68 minutes of diamond · layers = 8, next to 11 timed ones, not one every few seconds; the `core_chrisfile` pattern index is used by prefix counts (23 ms for 100k rows on a 1.95 M-row table); and the file browser's folder listing walks the `fname` index rather than the folder foreign key (523 ms for the first page of a 100k-file folder), which a code-point collation does not fix but an index on `(parent_folder_id, fname)` does (0.05 ms).

## 14. API pool leak after an overload (2026-10-06)

The API's failure to recover past the knee (§13) is a database connection leak in Django's error handling, triggered by the `DEBUG` setting the benchmark had inherited from `config.settings.local`. It did not come with the upgrade. The archived evidence is under [`history/locust_2026-10-06/`](history/locust_2026-10-06).

**Cause.** In the async request path Django renders an error response with `sync_to_async(response_for_exception, thread_sensitive=False)`, that is on the event loop's default executor rather than on the request's own thread (Django ticket #36027, fixed for Django 6.2, which is not released yet, and not backported). Under `DEBUG`, CUBE's `ResponseMiddleware` re-raises a view's exception, so each `PoolTimeout` of an overloaded step became a DEBUG 500 page rendered on an executor thread, and printing the QuerySets of its stack frames ran queries there. Django closes a request's connections when the request ends, on the request's thread; a connection opened on an executor thread is never closed, and executor threads live as long as the worker. Each worker's executor threads (20 on the 16-CPU box) took its 10 connections one at a time, and from then on every request that needed the database waited 10 s and failed while the server saw 40 idle connections. In a reproduction on a laptop (a 400-user step), a diagnostic that recorded the thread and call stack of every connection taken from the pool and not yet returned found all 40 held by executor threads, each taken in `django/views/debug.py` printing a QuerySet.

**Not the upgrade.** aeb4b94, built with the exact package versions of the pre-upgrade image (Django 5.2.9, asgiref 3.11.1, uvicorn 0.38.0, psycopg 3.3.4, psycopg-pool 3.3.1, Python 3.12.11), at the same envelope with `DEBUG` on, recovered after a 100-user step (250 RPS; 31 500s, 30 of them logins) and did not recover after a 400-user step: for all 18 probe rounds (about ten minutes, as each one waited out the timeouts) every request failed with a 500 after 10 s or got no answer, with 40 idle connections, as on 30fbbaf. The upgrade made the leak arrive sooner: September's single 100-user step (`recovery/`) served 10 RPS with 67% failures, and the sweep's 72.5%. In a directional A/B on a laptop with the same code, asgiref 3.12.1 instead of 3.11.1 alone took a 400-user step from 240 to 39 RPS, so more requests reach the pool timeout and render error pages; with 3.11.1 three of the four workers still lost all their connections. June's 200-user step probably served most requests because its earlier steps had not yet taken every connection, and its 400-user step probably left the stack broken too; nothing checked either then.

**Fix.**

- `core.middleware` backports Django's fix: error responses are rendered on the request's thread, so their connections are closed with the request's. It is installed from `Core.ready()` and does nothing from Django 6.2.
- The benchmark runs with `DEBUG` off (`CUBE_DEBUG`, default `false`), as production does. `DEBUG` also put every SQL statement through Django's query recorder and ran the debug toolbar's middleware on every request, so this moves every baseline (see below).
- `core.tests.test_middleware` serves concurrent failing requests under `DEBUG` through Django's ASGI handler and CUBE's middleware, and checks that the pool gets every connection back. Run on 30fbbaf with the pool-counter helper it uses added, it fails (two connections stranded); it passes with the fix. A second test drops clients while their requests hold, or wait for, a connection.

Separately, `psycopg-pool` went from 3.3.1 to 3.3.3 as maintenance: 3.3.3 stops a sync pool's worker threads from exiting after 24 hours without maintenance work (psycopg #1419). Django's pool queues such work every ten minutes, so CUBE is unlikely to have hit it, and it has nothing to do with the leak.

**Harness.** Each Locust step now records whether the API was healthy before it and whether it recovered after it, in `<csv prefix>_recovery.json` and two columns of the Locust report, and Locust exits with code 3 otherwise. The probe sends bursts of 16 concurrent requests on separate connections, which most likely reach every worker, where a single request can be answered by the one healthy worker; with `CUBE_DB_POOL_STATS_INTERVAL` set (5 s in the benchmark) it also requires every `uvicorn` worker to report a pool with no checked-out connection, which does make sure of all of them.

**Results.** The issue's single 100-user step, then probes every 10 s for three minutes: every request answered in 13–26 ms. The full read sweep on a fresh stack, without restarts between steps:

| Users | Requests | Failures | RPS | p50 / p95 / p99 (ms) | Recovered | 2026-09-17 fresh sweep: RPS, failures |
|---|---|---|---|---|---|---|
| 25 | 6,402 | 0 | 71 | 12 / 23 / 140 | yes, 0 s | 61, 0 |
| 50 | 11,874 | 41 | 132 | 10 / 26 / 470 | yes, 0 s | 97, 303 |
| 100 | 22,057 | 1,744 | 246 | 10 / 35 / 1,100 | yes, 0 s | 10, 678 |
| 200 | 37,342 | 5,147 | 416 | 34 / 190 / 3,000 | yes, 0 s | 27, 1,601 |
| 400 | 39,053 | 7,179 | 435 | 320 / 710 / 12,000 | yes, 0 s | 35, 2,115 |

After every step all four pools reported no checked-out connection, and three minutes of probes after the 400-user step answered in 11–23 ms. Of the 400-user step's failures, 311 are logins that failed with a 500 and 6,829 the 401s of the users those logins left without a token; 39 are other 500s. The login storm (§13) is now the first wall.

**Consequences.**

- The September Locust results from 100 users up measured a broken stack (§13). The control-plane knee of §4 (~50 users, p95 pinned at the 10 s pool timeout, in June as in September) is the leak's and `DEBUG`'s together, and no run separates the two: at 25 users, where nothing failed and so nothing leaked, p50 still fell from 29 to 12 ms. With both changed, throughput keeps rising to 400 users and most failures are logins.
- Turning `DEBUG` off moves every baseline. Runs up to 2026-09-17 had it on, and `bench-compare` reports `envelope.CUBE_DEBUG` as a caution against them. The two runs issue 1 ([#150](https://github.com/FNNDSC/HARBOR-planning/issues/150)) compares against were run again at the new envelope: `2026-10-07T002040Z` (linear · file_count, 1,731 s at 100,000 files against 1,766 s) and `2026-10-07T005703Z` (diamond · layers, 2,906 s at 8 layers against 3,260 s). `bench-compare` finds no regression against 041540Z and 072731Z, and the API p95 the harness measured during those runs was 28–51% lower at 9 of their 10 levels.
- Production runs with `DEBUG` off, where `ResponseMiddleware` turns a view's exception into its own 500 on the request's thread, so the September failure does not happen there in that form. One path remains: Django still logs error responses from the default executor, and with `ADMINS` set (production) the error email reports the request's user, which for a session-authenticated request queries the database on that thread. Django 6.2 does not change that call; it is left for later.

## 15. PostgreSQL configuration (2026-10-14)

Issue 1 ([#150](https://github.com/FNNDSC/HARBOR-planning/issues/150)) replaces the stock `postgres:18` configuration of both compose stacks with a committed `postgres/cube.conf`, sized for the benchmark's `db` limit (4 GiB, 2 CPUs), and adds migration `core.0004`, which vacuums and analyzes the file and folder tables sooner. [envelope.md](envelope.md) § "PostgreSQL configuration" lists each value and why; the main ones are `shared_buffers` 1GB, `work_mem` 32MB, `max_wal_size` 8GB, `checkpoint_timeout` 15min, `wal_compression` lz4 (the issue asked for `on`, which means pglz and costs far more CPU on a 2-CPU `db`) and `timezone` UTC. `db` also gets a 1 GB `/dev/shm`: at 32 MB `work_mem` a parallel hash join no longer fits in Docker's 64 MB default.

The harness now records what the server runs with and what it does. `environment.json` has every Postgres setting and each container's limits, and each scenario has deltas of checkpoints, WAL, full-page images, temp files, writes by process type and what the `db` container wrote, for its workload and its cleanup, with whole-run totals in `summary.json` ([envelope.md](envelope.md) § "What each run records about Postgres"). The figures below come from those counters; checkpoint causes come from the `db` log, and the WAL zero-fill of the before runs was read by hand from `pg_stat_io` at the end of each run.

**Protocol.** All runs were made in one session on the benchmark box, from 2026-10-13 23:38 to 2026-10-14 05:57 UTC, each on a fresh stack (`down -v`, plugin-job containers removed, `just bench-start`). The before runs are at 8ea010b: the stock configuration and the harness that records settings, limits and most counters, though not `wal_init_bytes` or the per-statement temp and WAL columns, which 2d52608 adds. The after runs are at 2d52608, the configuration. diamond · layers = 8 varied by about 10% between fresh-stack runs on 2026-09-17, enough to move a single pair's result, so it was run twice each way, alternating (before, after, before, after), and the criterion is judged on the means. All eight runs used `dbg-bigfiles` 1.0.0, `pl-simpledsapp` 2.1.5 and `pl-topologicalcopy` 1.0.13 (`workload_plugins` in `environment.json`); on a later commit `just bench-start` registers the same versions from the committed pin ([envelope.md](envelope.md) § "Pinned workload plugin versions").

| Command (`just bench-run --tier ...`) | Before | After |
|---|---|---|
| `smoke` | `2026-10-13T233911Z` | `2026-10-14T022103Z` |
| `full --topology linear --axis file_count --cap 100000 --repeat 1 --restart-on-fail` | `2026-10-13T234257Z` | `2026-10-14T022450Z` |
| `full --topology diamond --axis layers --cap 8 --repeat 1 --restart-on-fail` | `2026-10-14T001854Z`, `040048Z` | `2026-10-14T030059Z`, `045928Z` |

**Results.**

| Acceptance criterion | Before | After |
|---|---|---|
| Temp files during linear · file_count = 100000 (the 100,000-file level) | 166.2 MB, and 61.5 MB more in its cleanup | 0, and 0 in the whole run |
| Requested checkpoints during diamond · layers = 8, whole run | 19 and 21 (the `db` log names 18 and 21 as triggered by WAL size) | 0 and 0; the `db` log names only timed ones |
| What `db` wrote at diamond · layers = 8 (`peak_write_bytes.db`) | 30.47 and 32.34 GB, mean 31.41 GB | 18.91 and 18.80 GB, mean 18.85 GB: **−40.0%** (target −30%) |
| Effective settings in `environment.json` | — | in every run |
| `test-unit`, `test-integration`, `bench-run --tier smoke` | — | pass (see Tests) |

Against the earlier baselines of that command the drop is 35.1% (`2026-10-07T005703Z`, 29.05 GB, `DEBUG` off but run on a stack the linear run had used) and 42.4% (`2026-09-17T072731Z`, 32.74 GB, `DEBUG` on).

**Where the bytes went** (diamond · layers = 8, means of the two runs each way). The `pg_stat_io` rows count what Postgres handed to the kernel; a page rewritten before the kernel flushes it reaches the disk once, so these rows do not add up to what the container wrote.

| At 8 layers | Before | After |
|---|---|---|
| Table and index pages written by backends to free a buffer (`pg_stat_io`) | 22.96 GB | 5.53 GB |
| … written by the checkpointer and the background writer | 1.95 GB | 2.06 GB |
| WAL generated | 10.09 GB | 5.22 GB |
| Full-page images in it | 846k | 11.7k |
| Checkpoints written (`num_done`) | 21 | 1 |
| Checkpoint triggers counted, timed / requested (skipped checkpoints included) | 7 / 17 | 3 / 0 |
| Temp files | 1.54 GB | 1.07 GB |
| Zero-filling new WAL segments (see below) | at most about 1.1 GB | 4.04 GB |
| `db` wrote, net of that zero-fill | about 30.3 GB | 14.81 GB (about −51%) |
| Its cleanup: requested checkpoints; `db` wrote | 2.5; 3.88 GB | 0; 1.14 GB |
| Makespan | 2,898 s | 2,861 s |

Most of the saving is buffer evictions. With 128 MB of `shared_buffers`, registering layer 8's files filled the pool with dirty table and index pages, and backends had to write pages out to make room, many of them again and again as the next rows touched them. With 1 GB they mostly stay in memory until a checkpoint writes them once. The rest is the WAL: at `max_wal_size` 1GB a checkpoint completed every few minutes, 21 in the level, many in the middle of the large `INSERT … UNNEST` statements, and after each one every page those statements touched again went to the WAL in full. With one checkpoint completed during the level, the same work wrote 98.6% fewer full-page images, and lz4 compresses the ones that remain. Over the whole run, cleanups included, `db` wrote 43.9% less (35.87 → 20.12 GB).

**WAL zero-fill.** PostgreSQL writes zeros into every new 16 MB WAL segment before using it, and keeps old segments for reuse only up to about what recent checkpoints needed. At `max_wal_size` 1GB a fresh volume's pool stayed at 64 segments (1.16 and 1.11 GB zero-filled since the stack started); at 8GB it grew to 258 and 261 segments, 4.29 and 4.33 GB, of which 4.04 GB fell in the measured level each time. On a volume whose pool is already that large, the saving would be larger by about the zero-fill (−51% instead of −40%). How a larger, aged database changes the eviction saving was not measured: every run started from an empty database.

**Unchanged.** Every level that takes more than a minute moved by less than 2% (100,000 files: 1,719 → 1,724 s; 8 layers: 2,898 → 2,861 s), shorter ones by up to one 2 s poll interval either way, and `bench-compare` flags no makespan change. The time goes to registration, most of it outside Postgres: all the statements of the 100,000-file level take 90 s of its 1,724 s, and issue 4 ([#155](https://github.com/FNNDSC/HARBOR-planning/issues/155)) addresses the rest. The pre-submission scan of that output shows what `work_mem` buys and what it does not: its sort, which spilled before, now runs in memory and still takes 1.93 s per call instead of 2.10 s, because the cost is locale-aware comparison (issue 8b, [#160](https://github.com/FNNDSC/HARBOR-planning/issues/160)). API latency is within its noise: the worst p95 at 8 layers was 718 and 318 ms before, 353 and 355 ms after, and the latency flags `bench-compare` raised (one "regressed", three "improved") are each the p95 of a handful of requests. `db`'s memory use, page cache included, reached its 4.0 GiB limit in all four diamond runs, with no swap and no OOM kill; its CPU still peaks at its 2-CPU limit.

**What remains.** In diamond · layers = 8, cleanup included, three statements still spill to temp files, each because it handles hundreds of thousands of rows at once (from `pg_stats.json`, which now has each statement's temp and WAL bytes): Django's deletion collector (`parent_folder_id IN (…) ORDER BY fname DESC`, 354–657 MB over 148 calls), registration's bulk insert (1,638,400 rows in 10 statements, 644 MB; it also writes 4.39 of the 5.42 GB of WAL that the level and its cleanup wrote) and the pre-submission scan (`fname LIKE … ORDER BY fname DESC`, 422 MB over 64 calls). Issues 4 ([#155](https://github.com/FNNDSC/HARBOR-planning/issues/155)) and 6 ([#157](https://github.com/FNNDSC/HARBOR-planning/issues/157)) address all three. Until registration's inserts each finish in under a second, `log_min_duration_statement` logs them with every file path inlined, because Django binds parameters on the client: the `db` log grew to 816 MB in each diamond run on this configuration (135 KB before) and to 73 MB in the linear one.

**Tests.** On the final commit, 58285cf, on the benchmark box, both suites pass on the development stack with `cube.conf`: `just test-unit` (1,368 tests, 17 skipped, 1 expected failure) and `just test-integration` (77 tests, 34 skipped) on Docker, and the same two jobs as CI's podman job runs them, under rootless Podman 5.7 on Ubuntu 26.04 with the branch merged into `master` (same counts). Among them, `core.tests.test_models` checks that the server reads `cube.conf`, that its default time zone is the one Django connects with, and that migration `core.0004` applies and reverses. The smoke tier passes before and after, 10 levels each, with no level flagged.

**Consequences.**

- The after runs are the baselines for these three commands from here on; the epic's baseline table ([#148](https://github.com/FNNDSC/HARBOR-planning/issues/148)) is to be updated to point at them. Other commands get their own baseline run on this configuration when an issue needs one.
- `bench-compare` against any earlier run reports three cautions it did not before: `postgres` and `limits` "not recorded", and `envelope.CUBE_DB_SYNCHRONOUS_COMMIT` (shown as `—`, though those runs had PostgreSQL's default `on`). Against a run of this configuration, a differing setting is a caution of its own.
- The development stack runs on the same file, and CUBE's tests run on it (Tests above).

## 16. Shared cache, Dragonfly v2.0.2 and their envelope (2026-10-21)

Issue 1b ([#151](https://github.com/FNNDSC/HARBOR-planning/issues/151)) gives CUBE a shared cache: Django's `RedisCache` on a Dragonfly instance of its own, `dragonfly-cache` (`--cache_mode`, no snapshot), apart from the Celery broker `dragonflydb`, and the helpers that the queue, event-driven, failure-handling, control-plane and token-cache issues build on (`core/cache.py`: locks, once-per-window markers and a bounded counter of expiring leases, all of which fail open when the cache does not answer). It also moves the broker to Dragonfly v2.0.2, which the cache's Dragonfly runs too, and pins, in the benchmark envelope, the CPUs and memory of both Dragonflies and of `worker-periodic` and `celery-scheduler` ([envelope.md](envelope.md) § "Knobs (env vars, with defaults)"). Nothing in CUBE calls the helpers yet, so the runs below check that none of this changes what the harness measures; the issues that use the cache measure what it buys.

**Why a second Dragonfly.** One Dragonfly has one memory limit and one eviction policy for all its logical databases. On a v2.0.2 instance capped at 256 MB, filling a cache database made the server refuse the broker's `LPUSH` in database 0 with `Out of memory`, and the eviction mode a cache wants (`--cache_mode`) would evict Celery's queues instead. With the cache apart, the broker never evicts and keeps its snapshot, while the cache evicts when full and starts empty after a restart. The cache can then be stopped while the broker, and every task, keeps running (below), as the issue's criterion asks; with one shared server, stopping the cache would stop the broker too.

**Protocol.** All runs were made on the benchmark box from 2026-10-20 22:07 to 2026-10-21 04:23 UTC, in three steps of one commit each, and each started on a fresh stack except the smoke run with the cache stopped (`2026-10-21T032008Z`), which followed the cache's smoke run (`031631Z`) on its stack. At 5bc2e49 (the broker's image recorded in `environment.json`), an A/B of Dragonfly v1.38.0 against v2.0.2 through `DRAGONFLY_IMAGE`. At 1e94ddd (the cache), a smoke run and the outage checks. At 0c9223b (the envelope), an A/B with the eight new limits at `0` (none) against their defaults. In each A/B every command ran once per arm, linear · depth = 16 twice, and successive pairs alternated which arm went first. All runs used `dbg-bigfiles` 1.0.0, `pl-simpledsapp` 2.1.5 and `pl-topologicalcopy` 1.0.13 from 2d52608's `chrisomatic.yml`, the one uncommitted file ([history/README.md](history/README.md) lists every run).

| Command (`just bench-run --tier ...`) | v1.38.0 | v2.0.2 | no new limits | new limits |
|---|---|---|---|---|
| `smoke` | `2026-10-20T220727Z` | `221116Z` | `2026-10-21T032810Z` | `033213Z` |
| `full --topology linear --axis depth --cap 16 --repeat 1 --restart-on-fail` | `221843Z`, `225330Z` | `221502Z`, `225711Z` | `034001Z`, `041603Z` | `033616Z`, `041947Z` |
| `full --topology linear --axis feeds --cap 128 --repeat 1 --restart-on-fail` | `222226Z` | `223431Z` | `034345Z` | `035538Z` |
| `full --topology fanout_fanin --axis feeds --cap 64 --repeat 1 --restart-on-fail` | `224923Z` | `224055Z` | `041159Z` | `040756Z` |

**Results.**

| | v1.38.0 | v2.0.2 | no new limits | new limits |
|---|---|---|---|---|
| `smoke` | 10 PASS | 10 PASS, none flagged | 10 PASS | 10 PASS, none flagged against the cache's smoke run `2026-10-21T031631Z` |
| linear · depth = 16, 16 deep | 67.69, 67.79 s | 67.74, 67.69 s | 67.81, 68.78 s | 67.56, 66.47 s |
| linear · feeds = 128 | PASS; 128 feeds 308.0 s | FAIL at 64 | PASS; 128 feeds 312.1 s | FAIL at 128; 326.4 s |
| fanout_fanin · feeds = 64 | FAIL at 32 | FAIL at 64 | FAIL at 32 | FAIL at 32 |
| Duplicate submissions in pfcon's log (feeds, fanout) | 5, 2 | 5, 4 | 6, 2 | 8, 2 |
| Broker, highest CPU and memory over the arm's runs | 13.4%, 57 MiB | 14.4%, 48 MiB | 14.7%, 44 MiB | 7.0%, 28 MiB |

Every failure, in either arm of either A/B, is a `cancelled:inst-*` criterion in a run whose pfcon log has duplicate submissions: the race of the queue issue ([#152](https://github.com/FNNDSC/HARBOR-planning/issues/152)), which decides where the feeds walls land from run to run (as in §13). `bench-compare` flags the levels whose verdict that race flipped by their verdict, with makespans within 5%, and a makespan at one level only, linear · feeds = 16, which the v1.38.0 run took 47.9 s against 22.6–24.3 s in the other three runs of that command. Its p95 flags go both ways (five improved, four regressed over the ten pairs): eight are on levels of 8 to 30 measured requests, and the ninth, an improvement (266 to 160 ms), is that same level with the new limits, 86 requests. At the other levels both arms passed, the largest makespan move is 4.9 s (fanout_fanin at 16 feeds, 27.8 s without the new limits and 32.7 s with them, +18%, under `bench-compare`'s 20%). One run per arm cannot tell that from noise: the level's other two runs took 27.3 s (v2.0.2) and 30.9 s (v1.38.0), and the three repeats of `2026-09-17T113103Z` spanned 28.8–33.4 s. The `main2` queue peaks are close where they are large (at 64 feeds without and with the limits, 432 and 462; at 16 fanout_fanin feeds, 158 and 150, then 139 and 142) and vary where they are small (at 32 feeds, 49 and 74). The v1.38.0 smoke run is flagged on no level against the last baseline, `2026-10-14T022103Z`.

**The envelope.** Dragonfly runs one thread per CPU it is given and keeps 80% of its memory limit as its `maxmemory`; unconstrained, the broker ran 16 threads with a `maxmemory` of about 92 GiB, and with the limits 2 threads with a `maxmemory` of 819 MiB. Under the limits nothing came near them:

| Service | Limit | Highest CPU (one CPU = 100%) | Highest memory |
|---|---|---|---|
| `dragonflydb` | 2 CPUs, 1 GiB | 7.0% | 28 MiB |
| `dragonfly-cache` | 1 CPU, 512 MiB | 4.2% | 14 MiB |
| `worker-periodic` | 1 CPU, 1 GiB | 23.0% | 256 MiB |
| `celery-scheduler` | 0.5 CPU, 512 MiB | 2.9% | 113 MiB |

The broker uses less with 2 threads than with 16 (7.0% against 14.7% of a CPU, 28 against 44 MiB): idle, before each run, it held 24 MiB of resident memory with 2 threads and 40 MiB with 16. The headroom is for what the next issues add: markers per status check (#152), a lease per pfcon call ([#158](https://github.com/FNNDSC/HARBOR-planning/issues/158)), token and count lookups per API request ([#159](https://github.com/FNNDSC/HARBOR-planning/issues/159), [#161](https://github.com/FNNDSC/HARBOR-planning/issues/161)) and the event streams on the broker ([#153](https://github.com/FNNDSC/HARBOR-planning/issues/153)); their runs should read `dragonfly-cache`'s and the broker's use against these limits.

**Without the cache.** On the benchmark stack at 1e94ddd, with a probe process in `chris` calling the helpers every 0.5 s:

- `dragonfly-cache` stopped: 50 token-authenticated GETs of the API root all returned 200 (p50 6.6 ms, 6.8 ms with the cache up); a smoke run passed all 10 levels, and the workers kept running with unchanged start times. The probe went ahead without the cache (410 of its 499 rounds were degraded while it was stopped, 461 across the three outages) and logged one WARNING when it failed and one INFO when it answered again, 207.3 s later, counting the 1,271 calls that went ahead without it. This smoke run was started with `just bench-compose '--profile cube --profile bench run --rm --no-deps benchmark python -m benchmarks.run_bench --tier smoke'`, since `just bench-run` would have started the cache again.
- Paused (a hung server): the API's p50 stayed at 6.4 ms; the probe's slowest call took 0.502 s, the 0.5 s socket timeout, after which the helpers skipped the cache for 5 s at a time, with one WARNING and one INFO 27.0 s later.
- CUBE's services restarted while the cache was stopped: all started and the API answered. Each uvicorn worker and each Celery service logged one start-up line, `CUBE shared cache: dragonfly-cache:6379/0 does not answer (…); starting without it, …`: four from `chris`, one from each Celery service (beat's in the scripted count; the two workers' in a recheck 20 s after a restart, as the script had counted before they logged).
- A cache URL that names the broker's database stops start-up with `ImproperlyConfigured`.

**Tests.** At 1e94ddd on the benchmark box, on Docker: `just lock-check`; `just bench-test` (264 passed, 1 skipped); `just openapi` and its split variant with nothing on stderr that CI's check matches; `core.tests.test_cache` and `test_testrunner` (54 tests, 9.3 s), during which a session on the development database survived; `just test-unit` (1,422 tests, 17 skipped, 1 expected failure) and `just test-integration` (77 tests, 34 skipped). The same two jobs as CI's podman job runs them, under rootless Podman 5.7 on Ubuntu 26.04 with the branch merged into `master`, pass with the same counts. 0c9223b changes only the benchmark override and envelope.md; its runs are above.

**Consequences.**

- The "new limits" runs are the baselines for these four commands from here on: `smoke` `2026-10-21T033213Z`, linear · depth = 16 `033616Z` and `041947Z`, linear · feeds = 128 `035538Z` and fanout_fanin · feeds = 64 `040756Z`. Other commands get theirs when an issue needs one.
- Comparing a new run with a run from before this issue, `bench-compare` reports rows that come from this issue's changes to the stack, not from a change in performance. Which rows depends on how old the earlier run is:
  - Any earlier run: `images.dragonflydb` and `images.dragonfly-cache` as information (the broker's image changed and the cache is new), and `envelope.CUBE_CACHE_URL` as a caution (a new setting).
  - The 2026-10-13/14 runs, the first to record container limits: also a caution for each of the new limits (`limits.dragonflydb.cpus` and so on), and for the cache's other `limits.dragonfly-cache.*` rows, since those runs had no cache.
  - Runs before 2026-10-13, which recorded no limits: one `limits` row, "not recorded", in place of those.
  - Every earlier campaign: `host.mem_total_bytes`, because the box reports a few KiB less memory each campaign (12 KiB less than on 2026-10-14).

  Compared with the runs of this section, it reports only real differences.

## 17. Committed workload-plugin pin (2026-10-22)

Every campaign up to § 16 registered the workload plugins from an edited `chrisomatic/chrisomatic.yml`, uncommitted but for § 15's runs (the edit was on `master` between #739 and #744), because the committed file takes `pl-topologicalcopy` by name from the ChRIS store, which now serves 2.0.0 under that name — a no-op image, `docker.io/backplane/true`, declaring the three parameters the harness passes (1.0.13 also declares `pftelDB`) — and does not hold 1.0.13. `just bench-start` now registers them from the committed `benchmarks/chrisomatic/benchmark.yml`, and the harness refuses to start unless CUBE holds exactly those registrations ([envelope.md](envelope.md) § "Pinned workload plugin versions"). The runs below check that the pin changes nothing the harness measures, and give the four commands of § 16 baselines that record what ran.

**Which images.** Each plugin is pinned by the index digest of the image the archived baselines ran under its untagged reference (`latest`) on the benchmark box. The version tags are other builds of the same code:

| Plugin | Pinned: the baselines' image | The version tag's image |
|---|---|---|
| `dbg-bigfiles` 1.0.0 | `b956e35e…`, the 1.0.0 tag's | the same |
| `pl-simpledsapp` 2.1.5 | `c4e87262…`, built 2026-02-25 from master `bcf7449` | `45af8129…`, built 2026-02-09 from the tag, `e4750d6` |
| `pl-topologicalcopy` 1.0.13 | `35cb5798…`, the master build of `6d5111b` (CI run 25380445684) | `2e1b9cf1…`, the tag's own build of `6d5111b` (CI run 25380445870) |

The two builds of each plugin install identical `.py` files and packages and print identical `--json` descriptions; they differ only in `.git` and `.pyc` headers, and for `pl-simpledsapp` also in the README (and the `METADATA` that embeds it). `bcf7449` is one README-only commit after `e4750d6` ("docs: align README with current plugin behavior"): a plugin's `latest` moves with every master commit, so it pins nothing. 1.0.13 never reached the store because the tag build's upload step failed. chrisomatic 1.0.0, the last release, cannot pull a digest reference, so `just bench-start` pulls what the pin names first (`just bench-pull-plugins`) and chrisomatic registers the present image; `pl-simpledsapp` 2.1.4 and later have no arm64 image, so an arm64 laptop benchmarks with a pin of its own local builds (envelope.md).

**What the harness checks.** chrisomatic registers the version an image reports and uses an entry's `version` only to search CUBE, so the harness reads the same file and requires one registered version of each plugin (CUBE itself resolves `pl-topologicalcopy` by name), the pinned one under the pinned `dock_image`, and its image present where it can read the Docker daemon. Before the runs below, on the benchmark box at c4aadd6 with the change applied, three disturbances were each refused with the problem named: `bench-run` against a pin naming the 1.0.13 tag build's digest; `bench-start` with a pin registering `pl-simpledsapp` 2.1.5 again under its untagged reference (chrisomatic's 400, with `bench-start`'s hint); and `bench-run` after the store's 2.0.0 was registered next to 1.0.13. On the developer laptop (arm64, the containerd image store), with a pin naming the laptop's local builds under the references its development `chrisomatic.yml` uses, the development file run on the stack that pin had provisioned found the three registrations and failed nothing, and `bench-start` with the pin then changed nothing: the two files share one database. Each run now records each plugin's image (id, digests, architecture) and the pin's path and sha256, and `bench-compare` compares them: another name or version is a blocker, other digests a caution, another `dock_image` or pin information.

**Protocol.** All runs were made on the benchmark box on 2026-10-22 from 12:40 to 13:02 UTC at 0677a9c, the first runs since 2026-10-14 on a clean tree (`git.dirty` false), each on a fresh stack (`just bench-nuke`, `just bench-start`) with every envelope knob at its default: the four commands of § 16, linear · depth = 16 twice, second and last. `just bench-start` pulled nothing, since the pinned images were the box's own, and every run records one version of each plugin on those images (ids `1c451a28…`, `5f2bf3a1…`, `332956a3…`). Host as in § 16: kernel 7.0.0-38, Docker 29.9.1, Compose 5.6.0.

| Command (`just bench-run --tier ...`) | Run | § 16 baseline | Result |
|---|---|---|---|
| `smoke` | `2026-10-22T124103Z` | `2026-10-21T033213Z` | 10 PASS (10 PASS) |
| `full --topology linear --axis depth --cap 16 --repeat 1 --restart-on-fail` | `124505Z`, `125917Z` | `033616Z`, `041947Z` | PASS; 16 deep 68.65, 68.69 s (67.56, 66.47 s) |
| `full --topology linear --axis feeds --cap 128 --repeat 1 --restart-on-fail` | `124848Z` | `035538Z` | FAIL at 64 (`cancelled:inst-614`), 109.0 s; 3 duplicates (FAIL at 128; 108.4 s at 64; 8 duplicates) |
| `full --topology fanout_fanin --axis feeds --cap 64 --repeat 1 --restart-on-fail` | `125517Z` | `040756Z` | FAIL at 32 (`cancelled:inst-300`, `-308`, `-364`), 69.7 s; 4 duplicates (FAIL at 32, 70.2 s; 2 duplicates) |

**Results.** `bench-compare` calls each pair a caution for one reason, `workload_plugins.image` (the baselines recorded no image), with the `dock_image` strings, the pin, the commit, `git.dirty` and CUBE's image as information. It flags no makespan apart from the level whose verdict the duplicate-submission race flipped (linear · feeds = 64). The depth makespans lie within the 66.47–68.78 s of the eight earlier runs of that command; at a level both runs passed the largest increase is linear · feeds = 16, 22.6 → 25.8 s (+14%, under the 20% threshold; the four earlier runs took 22.6–24.3 s, and 47.9 s once), and the largest move a decrease, fanout_fanin · feeds = 16, 32.7 → 27.6 s (−15%; the earlier runs took 27.3–32.7 s). The feeds run's wall at 64 where its baseline reached 128 is the race's timing, as in § 16, where the v2.0.2 arm also failed at 64: in the fanout run the three cancelled instances are three of the four jobs pfcon logged as submitted twice (`container name … is already in use`); in the feeds run the cancelled instance, 614, was never submitted (pfcon logged nothing for it) and the three jobs submitted twice in that scenario ended `finishedSuccessfully`, which fits the race's stale status writes ([#152](https://github.com/FNNDSC/HARBOR-planning/issues/152)); the stack was reset before 614's parent could be read. `main2` peaks are close where they are large (438 against 462 at 64 feeds, 1,048 against 1,108 at 32 fanout_fanin feeds). The p95 flags lean the other way this time, seven regressed and two improved over the five pairs: six are on levels of 8 to 18 measured requests, and three are the slowest `create` requests of larger levels, linear · feeds = 8 and 16 and fanout_fanin · feeds = 32 (40, 80 and 192 creates), whose medians did not move (60.7 against 72.7 ms, 118.3 against 115.1 ms, 270.3 against 252.2 ms) while the same tail fell at other levels (linear · feeds = 32, 532 → 470 ms; fanout_fanin · feeds = 8, 116 → 92 ms). Against the spread of the four earlier runs of each command, three p95s lie well above it: linear · feeds = 1 (125 ms against 66–99, one `list` request of 159 ms), linear · feeds = 8 (181 against 96–114 ms) and fanout_fanin · feeds = 32 (542 against 433–507 ms). Nothing in this change runs during a scenario (the image lookups happen once, at start-up), the images are the baselines' own, and CUBE's code at 0677a9c differs from 0c9223b's only in comments, docstrings, line breaks and the wording of two of the cache helpers' error messages (which nothing calls yet); the next runs against these baselines will show whether that tail moved.

**Tests.** `just bench-test`: 287 passed on the laptop, and 286 passed and 1 skipped on the benchmark box. The change touches no CUBE code, and CI loads neither `docker-compose.benchmark.yml` nor the `bench-*` recipes; it was validated on Docker only (neither machine runs Podman).

**Consequences.**

- These runs are the baselines for the four commands from here on: `smoke` `2026-10-22T124103Z`, linear · depth = 16 `124505Z` and `125917Z`, linear · feeds = 128 `124848Z` (failed at 64 on duplicate submissions) and fanout_fanin · feeds = 64 `125517Z` (failed at 32 on duplicate submissions). Other commands get theirs when an issue needs one.
- Against any run archived before this section `bench-compare` reports `workload_plugins.image` as a caution and the `dock_image` strings and `workload_plugins_pin` as information; against the runs of this section it reports only what differs. Against the June runs, which recorded no workload plugins at all, it reports `workload_plugins` once instead.
