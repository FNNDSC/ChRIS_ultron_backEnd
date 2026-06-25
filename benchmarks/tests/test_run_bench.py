"""
Tests for benchmarks.run_bench — scenario params, tier filtering, level rollup, plugin resolution.
"""

import pytest

from benchmarks.config import load_tier
from benchmarks.models import (Classification, LevelResult, PluginRole, ScenarioParams,
                               ScenarioResult, StatusTimeline, Verdict)
from benchmarks.run_bench import (_filter_tier, _level_row, _override_baseline,
                                  ambiguous_plugins, apply_build_errors,
                                  build_workload_manifest, effective_poll_cadence,
                                  make_scenario_params, plugin_ambiguity_warning)


# -- scenario params -------------------------------------------------------------------

def test_make_scenario_params_overrides_only_one_axis():
    tier = load_tier("smoke")
    p = make_scenario_params(tier.baseline, 2.0, "linear", "depth", 8, 3)
    assert p.depth == 8 and p.axis == "depth" and p.level == 8 and p.repeat_index == 3
    assert p.feeds == tier.baseline.feeds            # other dims unchanged
    assert p.file_count == tier.baseline.file_count
    assert p.poll_interval == 2.0


def test_make_scenario_params_file_count_axis():
    tier = load_tier("smoke")
    p = make_scenario_params(tier.baseline, 1.0, "linear", "file_count", 100, 0)
    assert p.file_count == 100 and p.depth == tier.baseline.depth


# -- tier filtering --------------------------------------------------------------------

def test_filter_tier_topology_and_cap_override():
    f = _filter_tier(load_tier("full"), topology="linear", axis=None, cap=4, repeat=1)
    assert set(f.topology_axes) == {"linear"}
    assert all(cap == 4 for axes in f.topology_axes.values() for cap in axes.values())
    assert f.repeat == 1


def test_filter_tier_axis_drops_topologies_without_it():
    f = _filter_tier(load_tier("full"), topology=None, axis="layers", cap=None,
                     repeat=None)
    assert set(f.topology_axes) == {"diamond"}        # only diamond has a 'layers' axis


def test_filter_tier_rejects_unknown_topology_and_axis():
    with pytest.raises(ValueError, match="topology 'bogus'"):
        _filter_tier(load_tier("full"), topology="bogus", axis=None, cap=None,
                     repeat=None)
    with pytest.raises(ValueError, match="axis 'bogus'"):
        _filter_tier(load_tier("full"), topology=None, axis="bogus", cap=None,
                     repeat=None)


def test_override_baseline_replaces_only_given_fields():
    tier = load_tier("smoke")
    t2 = _override_baseline(tier, file_size="1MiB", sleep_length=None)
    assert t2.baseline.file_size == "1MiB"
    assert t2.baseline.sleep_length == tier.baseline.sleep_length
    assert _override_baseline(tier, None, None) is tier

    t3 = _override_baseline(tier, None, None, file_count=100)
    assert t3.baseline.file_count == 100               # the marquee preset override
    assert t3.baseline.file_size == tier.baseline.file_size


def test_file_count_override_yields_to_the_escalated_axis():
    # --file-count sets the baseline, but when file_count IS the escalated axis the
    # per-level value must still win; the override only holds for other axes.
    tier = _override_baseline(load_tier("smoke"), None, None, file_count=50)
    escalated = make_scenario_params(tier.baseline, 1.0, "linear", "file_count", 100, 0)
    assert escalated.file_count == 100                  # level wins over the override
    held = make_scenario_params(tier.baseline, 1.0, "linear", "depth", 4, 0)
    assert held.file_count == 50                        # override held while escalating depth


# -- build errors & cadence ------------------------------------------------------------

def test_apply_build_errors_escalates_to_fail():
    clean = Classification(Verdict.PASS)
    failed = apply_build_errors(clean, ["HTTP 400: bad"])
    assert failed.verdict is Verdict.FAIL
    assert "build_error:1" in failed.criteria
    
    # already-FAIL classifications keep their original criteria
    hard = Classification(Verdict.FAIL, ("no_progress",))
    assert apply_build_errors(hard, ["x"]) is hard
    assert apply_build_errors(clean, []) is clean


def test_effective_poll_cadence_scales_with_feeds():
    assert effective_poll_cadence(1.0, 1) == 1.0          # baseline cadence
    assert effective_poll_cadence(1.0, 64) == 3.2         # bounded observer load
    assert effective_poll_cadence(1.0, 1000) == 5.0       # capped
    assert effective_poll_cadence(2.0, 1) == 2.0          # never faster than base


# -- level rollup ----------------------------------------------------------------------

def _scenario(verdict, makespan, p95, cpu, n_completed, out_bytes):
    p = ScenarioParams("linear", "depth", 1, 1, "1KiB", 1, 1, 1, 1, 1, 0, 1.0, 0)
    tls = []

    for i in range(n_completed):
        tl = StatusTimeline(i, "k", PluginRole.DS)
        tl.final_status = "finishedSuccessfully"
        tls.append(tl)

    return ScenarioResult(
        p, Classification(verdict), makespan, [], tls,
        {"by_class": {"create": {"p95_ms": p95}}, "errors": 0, "status_5xx": 0},
        {"db": {"cpu_pct_peak": cpu}},
        {"registered_output_bytes": out_bytes}, 0.0, 1.0)


def test_level_row_aggregates_repeats():
    reps = [_scenario(Verdict.PASS, 5.0, 100, 40, 2, 1000),
            _scenario(Verdict.PASS, 7.0, 300, 80, 2, 2000)]
    row = _level_row(LevelResult("linear", "depth", 4, Verdict.PASS, (), reps))
    assert row["makespan_median_s"] == 6.0            # median(5, 7)
    assert row["makespan_min_s"] == 5.0               # cross-run spread estimate
    assert row["worst_p95_ms"] == 300                 # worst across repeats
    assert row["peak_cpu_pct"]["db"] == 80
    assert row["completed"] == 4                       # 2 per repeat x 2 repeats
    assert row["registered_output_bytes"] == 2000      # max across repeats


def test_level_row_excludes_job_containers_and_keeps_service_io():
    p = ScenarioParams("linear", "depth", 1, 1, "1KiB", 1, 1, 1, 1, 1, 0, 1.0, 0)
    res = {
        "db": {"kind": "service", "cpu_pct_peak": 70.0, "blkio_write_bytes": 2048},
        "chris-jid-1": {"kind": "job", "cpu_pct_peak": 250.0, "blkio_write_bytes": 999},
    }
    sr = ScenarioResult(p, Classification(Verdict.PASS), 1.0, [], [],
                        {"by_class": {}, "errors": 0, "status_5xx": 0}, res,
                        {"registered_output_bytes": 0}, 0.0, 1.0)
    row = _level_row(LevelResult("linear", "depth", 1, Verdict.PASS, (), [sr]))
    assert row["peak_cpu_pct"] == {"db": 70.0}         # ephemeral job container excluded
    assert row["peak_job_cpu_pct"] == 250.0            # surfaced as one aggregate
    assert row["peak_write_bytes"] == {"db": 2048}     # service disk write only


# -- workload plugins ------------------------------------------------------------------

def test_build_workload_manifest_carries_versions_keyed_by_role():
    plugins = {
        PluginRole.FS: {"id": 1, "name": "dbg-bigfiles", "version": "1.0.0",
                        "dock_image": "localhost/dbg-bigfiles", "matches": 1},
        PluginRole.TS: {"id": 9, "name": "pl-topologicalcopy", "version": "1.0.13",
                        "dock_image": "fnndsc/pl-topologicalcopy", "matches": 1},
    }
    m = build_workload_manifest(plugins)
    assert m["fs"] == {"name": "dbg-bigfiles", "version": "1.0.0", "id": 1,
                       "dock_image": "localhost/dbg-bigfiles", "matches": 1}
    assert m["ts"]["version"] == "1.0.13"


def test_ambiguous_plugins_flags_multiversion_only():
    plugins = {
        PluginRole.DS: {"id": 2, "name": "pl-simpledsapp", "version": "2.1.5",
                        "dock_image": "fnndsc/pl-simpledsapp", "matches": 2},
        PluginRole.FS: {"id": 1, "name": "dbg-bigfiles", "version": "1.0.0",
                        "dock_image": "localhost/dbg-bigfiles", "matches": 1},
    }
    assert ambiguous_plugins(plugins) == ["pl-simpledsapp"]
    plugins[PluginRole.DS]["matches"] = 1
    assert ambiguous_plugins(plugins) == []


def test_plugin_ambiguity_warning_message():
    assert plugin_ambiguity_warning(
        {PluginRole.FS: {"name": "dbg-bigfiles", "matches": 1}}) is None
    msg = plugin_ambiguity_warning(
        {PluginRole.TS: {"name": "pl-topologicalcopy", "matches": 2},
         PluginRole.FS: {"name": "dbg-bigfiles", "matches": 1}})
    assert msg and "pl-topologicalcopy" in msg and "first match" in msg
