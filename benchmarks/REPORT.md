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
- **Tune Postgres for the write-heavy registration path** — `db` reached 200%+ CPU and tens of GiB of WAL (write-ahead log) under deep DAGs; review WAL/checkpoint settings and `db` resourcing (§3.2, §8.2).

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

**Reproduce.** Environment and the pinned envelope are in §2.1 ([envelope.md](envelope.md) documents each knob). The core reproduction is two commands against the pinned `fslink` stack; the poll-interval sweep (§5), aging loop (§6), file-size sanity (§7), control-plane RED sweep (§4, `just bench-locust`), and the isolated clean-stack re-runs (§3.2 cliff, §3.3 long jobs) each take their own invocation, listed verbatim in `history/README.md`. Workload plugins were pinned to `dbg-bigfiles` 1.0.0, `pl-simpledsapp` 2.1.5, and `pl-topologicalcopy` 1.0.12; the harness binds each by name to the first match (CUBE's `-version` order), so the stack must hold exactly one version of each ([STRATEGY.md](STRATEGY.md) § Workload Plugins).

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
