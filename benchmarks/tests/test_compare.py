"""
Tests for benchmarks.compare — run comparability, deltas, trends, and the CI gate.
"""

from pathlib import Path

from benchmarks.compare import (DeltaPolicy, breaking_point_shifts, check_comparability,
                                classify_delta, compare_levels, compare_runs,
                                flag_counts, has_regressions, main, render_csv,
                                render_markdown, trend_tables)
from benchmarks.models import RunData
from benchmarks.results import ResultsStore

POLICY = DeltaPolicy()      # 20% relative, 2s makespan floor, 50ms latency floor


# -- fixtures ----------------------------------------------------------------------------

def _env(**over):
    env = {
        "matrix": {"workload_sha256": "abc", "thresholds": {"scenario_timeout_s": 600},
                   "repeat": 1},
        "storage_mode": "fslink",
        "api_auth_mode": "token",
        "envelope": {"CUBE_UVICORN_WORKERS": "4"},
        "host": {"ncpu": 16, "mem_total_bytes": 1024, "operating_system": "Ubuntu",
                 "architecture": "x86_64"},
        "git": {"commit": "aaa", "dirty": "false"},
        "noise_floor": {"health_p50_ms": 3.0},
    }
    env.update(over)
    return env


def _lvl(topology="linear", axis="depth", level=1, verdict="PASS",
         makespan=10.0, p95=100.0):
    return {"topology": topology, "axis": axis, "level": level, "verdict": verdict,
            "makespan_median_s": makespan, "worst_p95_ms": p95}


def _run(run_id, levels, breaking_points=(), env=None):
    return RunData(run_id=run_id, path=Path("/runs") / run_id,
                   environment=env if env is not None else _env(),
                   summary={"run_id": run_id, "breaking_points": list(breaking_points)},
                   levels=levels)


# -- comparability -----------------------------------------------------------------------

def test_identical_environments_are_comparable():
    c = check_comparability(_env(), _env())
    assert c.status == "comparable" and c.diffs == ()


def test_workload_hash_mismatch_is_blocker():
    other = _env(matrix={"workload_sha256": "zzz", "thresholds": {}, "repeat": 1})
    c = check_comparability(_env(), other)
    assert c.status == "not_comparable"
    assert any(d.field == "matrix.workload_sha256" and d.severity == "blocker"
               for d in c.diffs)


def test_auth_mode_mismatch_is_blocker():
    c = check_comparability(_env(), _env(api_auth_mode="basic"))
    assert c.status == "not_comparable"


def test_missing_fingerprint_is_warning_not_crash():
    old = _env()
    del old["matrix"]                       # run predates the workload fingerprint
    c = check_comparability(old, _env())
    sha = next(d for d in c.diffs if d.field == "matrix.workload_sha256")
    assert sha.severity == "warning"
    assert c.status in ("caution", "not_comparable")    # thresholds/repeat also differ


def test_envelope_and_noise_floor_are_cautions():
    other = _env(envelope={"CUBE_UVICORN_WORKERS": "8"},
                 noise_floor={"health_p50_ms": 97.0})
    c = check_comparability(_env(), other)
    assert c.status == "caution"
    fields = {d.field for d in c.diffs}
    assert "envelope.CUBE_UVICORN_WORKERS" in fields
    assert "noise_floor.health_p50_ms" in fields


def test_commit_difference_is_informational():
    c = check_comparability(_env(), _env(git={"commit": "bbb", "dirty": "false"}))
    assert c.status == "comparable"         # comparing commits is the point
    assert any(d.field == "git.commit" and d.severity == "info" for d in c.diffs)


# -- delta classification ------------------------------------------------------------------

def test_sub_floor_change_is_unchanged_despite_large_percent():
    # 0.5s -> 0.9s is +80% but under the 2s makespan floor (poll-cadence noise)
    assert classify_delta("makespan_median_s", 0.5, 0.9, POLICY).flag == "UNCHANGED"


def test_change_over_both_thresholds_is_flagged():
    d = classify_delta("makespan_median_s", 10.0, 15.0, POLICY)
    assert d.flag == "REGRESSED" and d.delta == 5.0 and d.pct == 50.0
    assert classify_delta("makespan_median_s", 15.0, 10.0, POLICY).flag == "IMPROVED"


def test_large_absolute_but_small_percent_is_unchanged():
    # +4s on a 100s makespan clears the floor but not the 20% threshold
    assert classify_delta("makespan_median_s", 100.0, 104.0, POLICY).flag == "UNCHANGED"


def test_zero_baseline_uses_floor_only():
    d = classify_delta("worst_p95_ms", 0.0, 80.0, POLICY)
    assert d.flag == "REGRESSED" and d.pct is None


def test_missing_values_flag_as_only_one_run():
    # one-sided values must not masquerade as UNCHANGED (CSV consumers filter on flags)
    assert classify_delta("worst_p95_ms", None, 80.0, POLICY).flag == "—"
    assert classify_delta("makespan_median_s", 5.0, None, POLICY).flag == "—"


# -- level joins & verdicts ------------------------------------------------------------------

def test_verdict_flip_flags_regardless_of_metrics():
    base = [_lvl(verdict="PASS")]
    cand = [_lvl(verdict="FAIL")]
    deltas = compare_levels(base, cand, POLICY)
    assert deltas[0].flag == "REGRESSED"
    deltas = compare_levels(cand, base, POLICY)
    assert deltas[0].flag == "IMPROVED"


def test_verdict_improvement_dominates_metric_regression():
    # pinned behavior: FAIL->PASS makes the level IMPROVED even though makespan
    # regressed past both thresholds — broken->working dominates, and the gate
    # must not fire (the metric rows still show the regression to the reader)
    base = [_lvl(verdict="FAIL", makespan=10.0)]
    cand = [_lvl(verdict="PASS", makespan=50.0)]
    deltas = compare_levels(base, cand, POLICY)
    assert deltas[0].metrics[0].flag == "REGRESSED"       # the metric itself
    assert deltas[0].flag == "IMPROVED"                   # the level
    assert not has_regressions(compare_runs(_run("A", base), _run("B", cand)))


def test_asymmetric_ladders_flag_as_only_one_run():
    base = [_lvl(level=1), _lvl(level=2), _lvl(level=4)]
    cand = [_lvl(level=1), _lvl(level=2)]     # candidate broke earlier
    deltas = compare_levels(base, cand, POLICY)
    assert [d.level for d in deltas] == [1, 2, 4]
    assert deltas[-1].flag == "—"
    assert flag_counts(deltas)["—"] == 1


# -- breaking-point shifts --------------------------------------------------------------------

def _bp(topology="linear", axis="depth", level=8):
    return {"topology": topology, "axis": axis, "level": level, "criteria": ["x"]}


def test_breaking_point_moving_down_is_regression():
    base = _run("A", [_lvl(level=1)], breaking_points=[_bp(level=8)])
    cand = _run("B", [_lvl(level=1)], breaking_points=[_bp(level=4)])
    shifts = breaking_point_shifts(base, cand)
    assert shifts[0].direction == "regressed"


def test_breaking_point_appearing_and_vanishing():
    clean = _run("A", [_lvl(level=1)])
    broken = _run("B", [_lvl(level=1)], breaking_points=[_bp(level=4)])
    assert breaking_point_shifts(clean, broken)[0].direction == "regressed"
    assert breaking_point_shifts(broken, clean)[0].direction == "improved"
    assert breaking_point_shifts(clean, clean)[0].direction == "unchanged"


def test_breaking_point_moving_up_is_improvement():
    base = _run("A", [_lvl(level=1)], breaking_points=[_bp(level=4)])
    cand = _run("B", [_lvl(level=1)], breaking_points=[_bp(level=16)])
    assert breaking_point_shifts(base, cand)[0].direction == "improved"


def test_has_regressions_gate():
    base = _run("A", [_lvl(verdict="PASS")])
    cand = _run("B", [_lvl(verdict="FAIL")])
    assert has_regressions(compare_runs(base, cand))
    assert not has_regressions(compare_runs(base, base))


def test_gate_fires_on_breaking_point_shift_alone():
    # all levels unchanged, but the wall moved down -> still a regression
    base = _run("A", [_lvl(level=1)], breaking_points=[_bp(level=8)])
    cand = _run("B", [_lvl(level=1)], breaking_points=[_bp(level=4)])
    comparison = compare_runs(base, cand)
    assert flag_counts(comparison.level_deltas)["REGRESSED"] == 0
    assert has_regressions(comparison)


# -- rendering ---------------------------------------------------------------------------

def test_render_markdown_headline_and_banner():
    base = _run("A", [_lvl(makespan=10.0)], breaking_points=[_bp(level=8)])
    cand = _run("B", [_lvl(makespan=15.0)], breaking_points=[_bp(level=4)],
                env=_env(api_auth_mode="basic"))
    md = render_markdown(compare_runs(base, cand))
    assert "NOT COMPARABLE" in md
    assert "REGRESSED" in md
    assert "Breaking-point shifts" in md
    assert "linear — depth" in md


def test_self_compare_is_all_unchanged():
    run = _run("A", [_lvl(level=1), _lvl(level=2)])
    comparison = compare_runs(run, run)
    assert comparison.comparability.status == "comparable"
    assert flag_counts(comparison.level_deltas)["UNCHANGED"] == 2
    assert not has_regressions(comparison)


def test_render_csv_is_tidy():
    run_a = _run("A", [_lvl()])
    run_b = _run("B", [_lvl(makespan=15.0)])
    csv = render_csv(compare_runs(run_a, run_b))
    lines = csv.splitlines()
    assert lines[0].startswith("topology,axis,level,metric,baseline,candidate")
    assert len(lines) == 3                  # header + one row per compared metric


def test_render_csv_marks_one_sided_levels():
    # an asymmetric ladder must not surface as UNCHANGED in the tidy CSV
    base = _run("A", [_lvl(level=1), _lvl(level=2)])
    cand = _run("B", [_lvl(level=1)])
    csv = render_csv(compare_runs(base, cand))
    level2_rows = [l for l in csv.splitlines() if l.startswith("linear,depth,2,")]
    assert level2_rows and all(",—," in row for row in level2_rows)
    assert not any("UNCHANGED" in row for row in level2_rows)


def test_trend_tables_track_metric_across_runs():
    runs = [_run("A", [_lvl(level=1, makespan=10), _lvl(level=2, makespan=20)]),
            _run("B", [_lvl(level=1, makespan=11)]),
            _run("C", [_lvl(level=1, makespan=12), _lvl(level=2, makespan=24)],
                 breaking_points=[_bp(level=4)])]
    tables = trend_tables(runs, "makespan_median_s")
    (axis_key, headers, rows), = tables
    assert axis_key == ("linear", "depth")
    assert headers == ["Level", "A", "B", "C"]
    assert rows[0] == [1, 10, 11, 12]
    assert rows[1] == [2, 20, None, 24]     # level missing in run B
    assert rows[-1] == ["breaking point", None, None, 4]


# -- CLI ---------------------------------------------------------------------------------

def _write_run(root, run_id, levels, breaking_points=(), env=None):
    store = ResultsStore(root, run_id=run_id)
    store.write_json("summary.json",
                     {"run_id": run_id, "breaking_points": list(breaking_points)})
    store.write_json("environment.json", env if env is not None else _env())
    store.append_jsonl("levels.jsonl", levels)
    return store.run_dir


def test_main_writes_artifacts_and_exit_codes(tmp_path):
    a = _write_run(tmp_path, "A", [_lvl(makespan=10.0)])
    b = _write_run(tmp_path, "B", [_lvl(makespan=15.0)])
    out = tmp_path / "cmp"

    assert main([str(a), str(b), "--out", str(out)]) == 0
    assert (out / "compare.md").exists() and (out / "compare.csv").exists()
    assert "REGRESSED" in (out / "compare.md").read_text()

    # the gate: regressed makespan -> exit 1
    assert main([str(a), str(b), "--out", str(out), "--fail-on-regression"]) == 1
    # self-compare stays clean
    assert main([str(a), str(a), "--out", str(out), "--fail-on-regression"]) == 0


def test_main_policy_flags_can_silence_a_regression(tmp_path):
    a = _write_run(tmp_path, "A", [_lvl(makespan=10.0)])
    b = _write_run(tmp_path, "B", [_lvl(makespan=15.0)])
    out = tmp_path / "cmp"
    code = main([str(a), str(b), "--out", str(out), "--fail-on-regression",
                 "--regress-pct", "60"])
    assert code == 0                        # +50% is below the raised threshold


def test_gate_fails_on_not_comparable_runs(tmp_path):
    # an incomparable pair must not gate green, even with clean deltas
    a = _write_run(tmp_path, "A", [_lvl()])
    b = _write_run(tmp_path, "B", [_lvl()], env=_env(api_auth_mode="basic"))
    out = tmp_path / "cmp"
    assert main([str(a), str(b), "--out", str(out)]) == 0                # no gate: informational
    assert main([str(a), str(b), "--out", str(out), "--fail-on-regression"]) == 1


def test_main_unknown_run_exits_2(tmp_path):
    a = _write_run(tmp_path, "A", [_lvl()])
    assert main([str(a), str(tmp_path / "no-such-run")]) == 2


def test_main_renders_trend_for_three_runs(tmp_path):
    paths = [_write_run(tmp_path, rid, [_lvl(makespan=10.0 + i)])
             for i, rid in enumerate(("A", "B", "C"))]
    out = tmp_path / "cmp"
    assert main([str(p) for p in paths] + ["--out", str(out)]) == 0
    md = (out / "compare.md").read_text()
    assert "## Trend — makespan_median_s across 3 runs" in md
    assert "| Level | A | B | C |" in md


def test_render_markdown_echoes_policy_thresholds():
    md = render_markdown(compare_runs(_run("A", [_lvl()]), _run("B", [_lvl()]),
                                      DeltaPolicy(regress_pct=60.0)))
    assert "Flag thresholds" in md and "60%" in md
