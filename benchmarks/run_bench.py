"""Composition root: wire the adapters and pure logic into a runnable benchmark.

This is the only module that knows about every other one. It builds the API client and
Docker client, resolves plugin ids, defines ``run_scenario`` (execute -> sample -> poll
-> aggregate -> classify -> persist -> clean up) and drives the escalation engine,
persisting artifacts and rendering the report.

Run inside the benchmark container:  ``python -m benchmarks.run_bench --tier smoke``
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from collections import Counter
from dataclasses import replace

from . import classifier, environment, escalation, metrics, report, topologies
from .broker import BrokerClient
from .chris_api import ChrisApi
from .config import Tier, load_tier, step_for, tier_fingerprint
from .docker_client import DockerClient
from .pg_stats import PgStatStatements
from .executor import build_feeds
from .metrics import MetricSink
from .models import (BreakingPoint, Classification, LevelResult, PluginRole,
                     ScenarioParams, ScenarioResult, Verdict)
from .poller import ProgressProbe, poll_to_completion
from .recovery import recover_after_failure, wait_for_health, wait_for_quiescence
from .results import ResultsStore, default_results_root
from .units import parse_size


PLUGIN_NAMES = {PluginRole.FS: "dbg-bigfiles",
                PluginRole.DS: "pl-simpledsapp",
                PluginRole.TS: "pl-topologicalcopy"}

STATS_INTERVAL_S = 2.0

RESTART_SERVICES = ("chris", "worker-mains", "worker-periodic", "celery-scheduler")


class BenchmarkRunner:
    def __init__(self, *, url: str, username: str, password: str, tier: Tier,
                 store: ResultsStore, cube_poll_interval: float,
                 project: str | None = None, cleanup: bool = True,
                 restart_on_fail: bool = False, api_timeout: float = 30.0,
                 startup_health_timeout: float = 60.0):
        self.tier = tier
        self.store = store
        self.cube_poll_interval = cube_poll_interval
        self.cleanup = cleanup
        self.restart_on_fail = restart_on_fail
        self._sink = MetricSink()

        self.api = ChrisApi(url, username, password, timeout=api_timeout,
                            observer=self._record_request)
       
        # the base compose healthcheck is a no-op, so gate on real readiness ourselves
        if not wait_for_health(self.api, startup_health_timeout):
            raise RuntimeError(
                f"CUBE not reachable at {url} after {startup_health_timeout:.0f}s")
        
        self.docker = DockerClient(project=project, exclude_services=("benchmark",))
        
        broker_host, _, broker_port = os.environ.get(
            "BENCH_BROKER", "dragonflydb:6379").partition(":")
        
        self.broker = BrokerClient(broker_host, int(broker_port or 6379))
        self.pg_stats = PgStatStatements(self.docker)
        
        self.plugins = {role: self.api.get_plugin(name)
                        for role, name in PLUGIN_NAMES.items()}
        self.plugin_ids = {role: p["id"] for role, p in self.plugins.items()}

        warning = plugin_ambiguity_warning(self.plugins)
        if warning:
            print(warning, flush=True)

    def _record_request(self, record) -> None:
        self._sink.record_request(record)

    # -- escalation glue -------------------------------------------------------------

    def make_params(self, topology: str, axis: str, level: int,
                    repeat_index: int) -> ScenarioParams:
        return make_scenario_params(self.tier.baseline, self.cube_poll_interval,
                                    topology, axis, level, repeat_index)

    def run_scenario(self, params: ScenarioParams) -> ScenarioResult:
        from .stats_sampler import StatsSampler

        self._sink = MetricSink()                      # isolate this scenario's events
        topo = topologies.build(params.topology, params)
        before_counts = self._global_counts()
        poll_every = effective_poll_cadence(self.tier.poll_every_s, params.feeds)
        self.pg_stats.reset()                          # per-scenario query attribution
        started = time.time()

        with StatsSampler(self.docker, self._sink, interval=STATS_INTERVAL_S,
                          broker=self.broker):
            builds = build_feeds(self.api, topo, params.feeds, self.plugin_ids)
            feeds = [b.feed for b in builds if b.feed is not None]
            instances = [ref for b in builds for ref in b.instances]
            build_errors = [b.error for b in builds if b.error]
           
            poll = poll_to_completion(
                self.api, [f.feed_id for f in feeds], instances,
                poll_every=poll_every,
                scenario_timeout=self.tier.thresholds.scenario_timeout_s,
                no_progress_timeout=self.tier.thresholds.no_progress_timeout_s,
                progress_probe=ProgressProbe(self.docker))

        ended = time.time()
        db_deltas = self._db_deltas(before_counts, feeds)   # before cleanup deletes them
        red = metrics.red_rollup(self._sink.requests())
        resources = metrics.resource_rollup(self._sink.resources())
        queues = metrics.queue_rollup(self._sink.queues())
        
        classification = apply_build_errors(
            classifier.classify(poll, red, self.tier.thresholds), build_errors)

        result = ScenarioResult(
            params=params, classification=classification, makespan_s=poll.makespan_s,
            feeds=feeds, timelines=poll.timelines, red=red, resources=resources,
            db_deltas=db_deltas, started_at=started, ended_at=ended, queues=queues,
            notes=build_errors)

        if self.cleanup:
            self._cleanup_and_quiesce(feeds, before_counts, result.notes)
        
        # persist after cleanup so delete/quiesce traffic reaches api_requests.jsonl
        # and cleanup anomalies land in the scenario's notes
        self._persist_scenario(result, poll_every)
        return result

    # -- persistence -----------------------------------------------------------------

    def _persist_scenario(self, result: ScenarioResult, poll_every: float) -> None:
        sid = result.params.scenario_id()
        phases = metrics.timelines_rollup(result.timelines)
        requests = self._sink.requests()
        self.store.scenario_dir(sid)
        
        self.store.write_json(f"scenarios/{sid}/scenario.json", {
            "params": result.params, "verdict": result.classification.verdict,
            "criteria": list(result.classification.criteria),
            "makespan_s": result.makespan_s, "red": result.red,
            "resources": result.resources, "phases": phases,
            "db_deltas": result.db_deltas,
            "feeds": [f.feed_id for f in result.feeds], "notes": result.notes,
            "queues": result.queues,
            "observer": {            # the harness's own measurement traffic, made visible
                "poll_requests": sum(1 for r in requests if r.endpoint_class == "poll"),
                "poll_every_s": poll_every,
            },
            "duration_s": round(result.ended_at - result.started_at, 2)})
        
        pg_top = self.pg_stats.snapshot()
        if pg_top:
            self.store.write_json(f"scenarios/{sid}/pg_stats.json", pg_top)
        
        self.store.append_jsonl("api_requests.jsonl",
                                ({"scenario": sid, **r.__dict__} for r in requests))
        
        self.store.append_jsonl("docker_stats.jsonl",
                                ({"scenario": sid, **s.__dict__}
                                 for s in self._sink.resources()))
        
        self.store.append_jsonl("queue_depths.jsonl",
                                ({"scenario": sid, **q.__dict__}
                                 for q in self._sink.queues()))
        
        self.store.append_jsonl("status_samples.jsonl", (
            {"scenario": sid, "instance_id": tl.instance_id, "node": tl.node_key,
             "role": tl.role.value if tl.role else None,
             "first_seen": tl.first_seen, "final_status": tl.final_status}
            for tl in result.timelines))

    def _on_level(self, level: LevelResult) -> None:
        self.store.append_jsonl("levels.jsonl", [_level_row(level)])

    def _on_fail(self, level: LevelResult) -> None:
        # repeats short-circuit on FAIL, so the failing repeat is always the last one;
        # its scenario dir is where scenario.json already lives
        sid = (level.repeats[-1].params.scenario_id() if level.repeats
               else f"{level.topology}_{level.axis}-{level.level}")
        
        out_dir = self.store.scenario_dir(sid)
        
        summary = recover_after_failure(
            self.docker, self.api, out_dir, services=RESTART_SERVICES,
            restart=self.restart_on_fail,
            health_timeout=self.tier.thresholds.healthcheck_timeout_s)
        
        self.store.write_json(f"scenarios/{sid}/failure.json",
                              {"criteria": list(level.criteria), "recovery": summary})

    def _cleanup_and_quiesce(self, feeds, before_counts: dict, notes: list) -> None:
        """
        Delete the scenario's feeds and wait for CUBE to settle back to the
        pre-scenario baseline. Feed deletion is asynchronous, so returning as soon as
        the DELETEs are accepted would let deletion churn bleed into the next level's
        measurements; anomalies are recorded in the scenario's notes.
        """
        failed = 0
        for feed in feeds:
            try:
                if not self.api.delete_feed(feed.feed_id):
                    failed += 1
            except Exception:                          # noqa: BLE001 - best effort
                failed += 1

        if failed:
            notes.append(f"cleanup_delete_failed:{failed}")

        if feeds and not wait_for_quiescence(self._global_counts, before_counts,
                                             self.tier.thresholds.quiesce_timeout_s):
            notes.append(
                f"quiesce_incomplete_after_{self.tier.thresholds.quiesce_timeout_s}s")

    def _global_counts(self) -> dict:
        return {"feeds": self.api.feed_count(), "instances": self.api.instance_count(),
                "files": self.api.file_count()}

    def _db_deltas(self, before: dict, feeds) -> dict:
        """
        Feed/instance/file count deltas plus the absolute totals after the scenario
        (read before cleanup deletes the feeds). The absolutes are the x-axis for
        state-aging analysis: probe latency as a function of accumulated DB rows.
        """
        after = self._global_counts()
        output_bytes = 0

        for feed in feeds:
            for inst in self.api.get_feed_instances(feed.feed_id):
                output_bytes += int(inst.get("size") or 0)

        return {
            "feeds_delta": after["feeds"] - before["feeds"],
            "instances_delta": after["instances"] - before["instances"],
            "files_delta": after["files"] - before["files"],
            "feeds_total": after["feeds"],
            "instances_total": after["instances"],
            "files_total": after["files"],
            "registered_output_bytes": output_bytes,
        }

    # -- top-level run ---------------------------------------------------------------

    def run(self) -> dict:
        env = environment.collect_environment(self.docker)
        self._sink = MetricSink()  # keep noise-floor probes out of scenarios
        
        env["noise_floor"] = environment.measure_noise_floor(self.api)
        
        # 'basic' here means per-request password hashing inflated every number — the
        # report surfaces it so a degraded run can't masquerade as a clean one
        env["api_auth_mode"] = self.api.auth_mode
        
        # effective-workload identity: bench-compare uses this to decide whether two
        # runs are comparable at all
        env["matrix"] = tier_fingerprint(self.tier)
        
        env["attribution"] = {
            "queue_sampling": True if self.broker.available
            else self.broker.unavailable_reason,
            "pg_stat_statements": True if self.pg_stats.available
            else self.pg_stats.unavailable_reason,
        }

        # exact workload-plugin versions the run resolved to (the harness picks by
        # name, so without this there is no record of which version actually ran)
        env["workload_plugins"] = build_workload_manifest(self.plugins)
        env["workload_plugins_ambiguous"] = ambiguous_plugins(self.plugins)

        self.store.write_json("environment.json", env)

        levels, breaking = escalation.run(
            self.tier.topology_axes, self.tier.repeat, self.run_scenario,
            self.make_params, on_level=self._on_level, on_fail=self._on_fail,
            step_for=step_for)

        summary = {
            "run_id": self.store.run_id, "tier": self.tier.name,
            "environment": env, "levels_run": len(levels),
            "breaking_points": [_bp_row(bp) for bp in breaking],
            "verdict_counts": dict(Counter(lv.verdict.value for lv in levels)),
        }

        self.store.write_json("summary.json", summary)
        level_rows = self.store.read_jsonl("levels.jsonl")
        self.store.write_text("report.md", report.render(summary, level_rows))
        self.store.write_text("levels.csv", report.render_levels_csv(level_rows))
        return summary


# -- pure helpers ----------------------------------------------------------------------

def apply_build_errors(classification: Classification, build_errors: list) -> Classification:
    """
    A DAG that could not be fully created (e.g. a 4xx) is a hard failure for the
    level, even if everything that *was* created completed cleanly.
    """
    if build_errors and classification.verdict is not Verdict.FAIL:
        return Classification(
            Verdict.FAIL,
            classification.criteria + (f"build_error:{len(build_errors)}",))
    return classification


def effective_poll_cadence(base: float, feeds: int) -> float:
    """
    Observation cadence for a scenario. The poller issues one search per feed per
    cycle, so a fixed cadence makes the harness's own traffic grow linearly with the
    feeds axis; slowing the cadence as feeds escalate keeps observer load roughly
    bounded (~20 req/s) at the cost of coarser phase timing — which is already
    cadence-limited by design.
    """
    return max(base, min(5.0, feeds * 0.05))


def make_scenario_params(baseline, poll_interval: float, topology: str, axis: str,
                         level: int, repeat_index: int) -> ScenarioParams:
    """
    OFAT: take the tier baseline and override exactly the escalated axis with level.
    """
    b = baseline.as_dict()
    b[axis] = level

    return ScenarioParams(
        topology=topology, axis=axis, level=level, file_count=b["file_count"],
        file_size=b["file_size"], depth=b["depth"], branches=b["branches"],
        layers=b["layers"], merges=b["merges"], feeds=b["feeds"],
        sleep_length=b["sleep_length"], poll_interval=poll_interval,
        repeat_index=repeat_index)


def _level_row(level: LevelResult) -> dict:
    reps = level.repeats
    makespans = [r.makespan_s for r in reps if r.makespan_s is not None]
    p95s = [_worst_p95(r.red) for r in reps]
    peak_cpu: dict[str, float] = {}             # service containers only
    peak_write: dict[str, int] = {}             # service containers only
    peak_job_cpu = 0.0                           # one aggregate over job containers
    peak_queue: dict[str, int] = {}
    final = Counter()

    for r in reps:
        for svc, m in r.resources.items():
            if m.get("kind") == "job":          # collapse ephemeral chris-jid-* jobs
                peak_job_cpu = max(peak_job_cpu, m.get("cpu_pct_peak", 0.0))
                continue
            
            peak_cpu[svc] = max(peak_cpu.get(svc, 0.0), m.get("cpu_pct_peak", 0.0))
            peak_write[svc] = max(peak_write.get(svc, 0), m.get("blkio_write_bytes", 0))
        
        for q, m in r.queues.items():
            peak_queue[q] = max(peak_queue.get(q, 0), m.get("depth_peak", 0))
        
        for tl in r.timelines:
            if tl.final_status:
                final[tl.final_status] += 1
    
    return {
        "topology": level.topology, "axis": level.axis, "level": level.level,
        "verdict": level.verdict.value, "criteria": list(level.criteria),
        "repeats": len(reps),
        "makespan_median_s": round(statistics.median(makespans), 2) if makespans else None,
        "makespan_min_s": round(min(makespans), 2) if makespans else None,
        "makespan_max_s": round(max(makespans), 2) if makespans else None,
        "worst_p95_ms": max(p95s) if p95s else 0.0,
        "errors": sum(r.red.get("errors", 0) for r in reps),
        "status_5xx": sum(r.red.get("status_5xx", 0) for r in reps),
        "completed": final.get("finishedSuccessfully", 0),
        "final_status_counts": dict(final),
        "peak_cpu_pct": {k: round(v, 1) for k, v in peak_cpu.items()},
        "peak_job_cpu_pct": round(peak_job_cpu, 1),
        "peak_write_bytes": peak_write,
        "peak_queue_depth": peak_queue,
        "registered_output_bytes": max(
            (r.db_deltas.get("registered_output_bytes", 0) for r in reps), default=0),
    }


def _worst_p95(red: dict) -> float:
    return max((c.get("p95_ms", 0.0) for c in red.get("by_class", {}).values()),
               default=0.0)


def _bp_row(bp: BreakingPoint) -> dict:
    return {"topology": bp.topology, "axis": bp.axis, "level": bp.level,
            "criteria": list(bp.criteria)}


def build_workload_manifest(plugins: dict) -> dict:
    """
    Per-role workload-plugin provenance for the environment manifest:
    ``{role.value: {name, version, id, dock_image, matches}}``. ``matches`` is how
    many installed versions the name resolved to (>1 = the selection was ambiguous).
    """
    return {role.value: {"name": p["name"], "version": p["version"],
                         "id": p["id"], "dock_image": p["dock_image"],
                         "matches": p["matches"]}
            for role, p in plugins.items()}


def ambiguous_plugins(plugins: dict) -> list[str]:
    """
    Names that resolved to more than one installed version — the harness then runs
    CUBE's first match, which may not be the intended version.
    """
    return [p["name"] for p in plugins.values() if p.get("matches", 1) > 1]


def plugin_ambiguity_warning(plugins: dict) -> str | None:
    """
    Operator warning when any workload plugin resolved to more than one installed
    version (the harness then runs CUBE's first match, which may not be the intended
    one), else ``None``.
    """
    names = ambiguous_plugins(plugins)

    if not names:
        return None
    return (f"[bench] WARNING: multiple installed versions for {', '.join(names)}; "
            f"running CUBE's first match (highest -version). Runs may not be "
            f"reproducible — keep one version per workload plugin (see chrisomatic.yml).")


# -- CLI -------------------------------------------------------------------------------

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _size_arg(text: str) -> str:
    parse_size(text)  # validate eagerly; the harness keeps the original string
    return text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CUBE load & scalability benchmark (data plane)")
    p.add_argument("--tier", default="smoke",
                   help="matrix tier: smoke | default | full | "
                        "aging-grow | aging-probe")
    p.add_argument("--matrix", default=None, help="path to matrix.yml")
    p.add_argument("--topology", default=None,
                   help="restrict to one topology (linear|fanout_fanin|diamond)")
    p.add_argument("--axis", default=None, help="restrict to one escalation axis")
    p.add_argument("--repeat", type=int, default=None, help="override tier repeat count")
    p.add_argument("--cap", type=int, default=None, help="override every axis cap")
    p.add_argument("--file-size", type=_size_arg, default=None,
                   help="override baseline file size, e.g. 1MiB (the 2-point size "
                        "sanity check; fslink hides byte-copy cost)")
    p.add_argument("--file-count", type=int, default=None,
                   help="override baseline file count (held while escalating a "
                        "non-file_count axis; e.g. the heavy combined-stress feeds run)")
    p.add_argument("--sleep-length", type=float, default=None,
                   help="override baseline simpledsapp sleepLength in seconds "
                        "(long-active-job workload class)")
    p.add_argument("--poll-interval", type=float,
                   default=_env_float("CUBE_CELERY_POLL_INTERVAL", 2.0),
                   help="CUBE poll interval to record (set via compose env)")
    p.add_argument("--url", default=os.environ.get("CUBE_URL",
                                                    "http://chris:8000/api/v1/"))
    p.add_argument("--username", default=os.environ.get("CUBE_USERNAME", "chris"))
    p.add_argument("--password", default=os.environ.get("CUBE_PASSWORD", "chris1234"))
    p.add_argument("--results-dir", default=str(default_results_root()))
    p.add_argument("--no-cleanup", action="store_true",
                   help="keep created feeds (study cumulative-growth effects)")
    p.add_argument("--restart-on-fail", action="store_true",
                   help="restart services if health does not recover after a failure")
    return p


def _filter_tier(tier: Tier, topology: str | None, axis: str | None,
                 cap: int | None, repeat: int | None) -> Tier:
    topology_axes = tier.topology_axes

    if topology:
        if topology not in topology_axes:
            raise ValueError(f"topology {topology!r} not in tier {tier.name!r} "
                             f"(have: {sorted(topology_axes)})")
        topology_axes = {topology: topology_axes[topology]}
    
    if axis:
        topology_axes = {t: {axis: axes[axis]} for t, axes in topology_axes.items()
                         if axis in axes}
        if not topology_axes:
            raise ValueError(f"axis {axis!r} not in any selected topology of tier "
                             f"{tier.name!r}")
    if cap is not None:
        topology_axes = {t: {a: cap for a in axes} for t, axes in topology_axes.items()}
    
    return Tier(name=tier.name, baseline=tier.baseline, thresholds=tier.thresholds,
                repeat=repeat if repeat is not None else tier.repeat,
                poll_every_s=tier.poll_every_s, topology_axes=topology_axes)


def _override_baseline(tier: Tier, file_size: str | None,
                       sleep_length: float | None,
                       file_count: int | None = None) -> Tier:
    """
    Apply CLI baseline overrides (the file-size sanity check, the long-active-job
    workload class, and the baseline file count) without editing matrix.yml.
    """
    changes = {}

    if file_size is not None:
        changes["file_size"] = file_size

    if sleep_length is not None:
        changes["sleep_length"] = sleep_length

    if file_count is not None:
        changes["file_count"] = file_count

    if not changes:
        return tier
    return replace(tier, baseline=replace(tier.baseline, **changes))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tier = _filter_tier(load_tier(args.tier, args.matrix), args.topology, args.axis,
                        args.cap, args.repeat)
    tier = _override_baseline(tier, args.file_size, args.sleep_length, args.file_count)
    store = ResultsStore(args.results_dir)
    
    runner = BenchmarkRunner(
        url=args.url, username=args.username, password=args.password, tier=tier,
        store=store, cube_poll_interval=args.poll_interval,
        project=os.environ.get("COMPOSE_PROJECT_NAME"),
        cleanup=not args.no_cleanup, restart_on_fail=args.restart_on_fail)

    print(f"[bench] run {store.run_id} tier={tier.name} -> {store.run_dir}", flush=True)
    summary = runner.run()
    
    print(f"[bench] done: {summary['levels_run']} levels, "
          f"{len(summary['breaking_points'])} breaking point(s)", flush=True)
    
    print(f"[bench] report: {store.run_dir / 'report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
