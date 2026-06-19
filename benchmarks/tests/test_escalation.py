from benchmarks import escalation
from benchmarks.models import (Classification, ScenarioParams, ScenarioResult, Verdict)


def _params(topology, axis, level, i):
    return ScenarioParams(topology=topology, axis=axis, level=level, file_count=1,
                          file_size="1KiB", depth=1, branches=1, layers=1, merges=1,
                          feeds=1, sleep_length=0, poll_interval=1.0, repeat_index=i)


def _result(params, verdict, criteria=()):
    return ScenarioResult(params=params, classification=Classification(verdict, criteria),
                          makespan_s=1.0, feeds=[], timelines=[], red={}, resources={},
                          db_deltas={}, started_at=0.0, ended_at=1.0)


def _runner(fail_at_level=None, verdict_at=None):
    """
    Fake run_scenario: FAIL once `level >= fail_at_level`, else PASS.
    """
    def run_scenario(params):
        if verdict_at is not None:
            return _result(params, verdict_at(params.level), ("x",))
        v = (Verdict.FAIL if fail_at_level and params.level >= fail_at_level
             else Verdict.PASS)
        return _result(params, v, ("boom",) if v is Verdict.FAIL else ())
    return run_scenario


def test_aggregate_verdict_is_worst_of():
    p = _params("linear", "depth", 1, 0)
    reps = [_result(p, Verdict.PASS), _result(p, Verdict.DEGRADED, ("p95",)),
            _result(p, Verdict.PASS)]
    verdict, criteria = escalation.aggregate_verdict(reps)
    assert verdict is Verdict.DEGRADED
    assert criteria == ("p95",)


def test_escalate_axis_stops_at_first_fail():
    seen_levels = []
    levels, bp = escalation.escalate_axis(
        "linear", "depth", cap=64, repeat=1,
        run_scenario=_runner(fail_at_level=8), make_params=_params,
        on_level=lambda lr: seen_levels.append(lr.level),
    )
    assert seen_levels == [1, 2, 4, 8]        # binary escalation, stopped at 8
    assert bp is not None
    assert (bp.topology, bp.axis, bp.level) == ("linear", "depth", 8)
    assert bp.criteria == ("boom",)


def test_escalate_axis_respects_cap_without_fail():
    levels, bp = escalation.escalate_axis(
        "linear", "depth", cap=4, repeat=1,
        run_scenario=_runner(fail_at_level=None), make_params=_params,
    )
    assert [l.level for l in levels] == [1, 2, 4]
    assert bp is None


def test_on_fail_hook_called_once():
    calls = []
    escalation.escalate_axis(
        "linear", "depth", cap=16, repeat=1,
        run_scenario=_runner(fail_at_level=2), make_params=_params,
        on_fail=lambda lr: calls.append(lr.level),
    )
    assert calls == [2]


def test_fail_short_circuits_remaining_repeats():
    ran = []

    def run_scenario(params):
        ran.append((params.level, params.repeat_index))
        v = Verdict.FAIL if params.level >= 4 else Verdict.PASS
        return _result(params, v, ("boom",) if v is Verdict.FAIL else ())

    levels, bp = escalation.escalate_axis(
        "linear", "depth", cap=8, repeat=3,
        run_scenario=run_scenario, make_params=_params)
    # passing levels run all 3 repeats; the failing level stops after its first repeat
    assert ran == [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2), (4, 0)]
    assert bp.level == 4
    assert len(levels[-1].repeats) == 1


def test_escalate_axis_decade_step():
    seen = []
    levels, bp = escalation.escalate_axis(
        "linear", "file_count", cap=1000, repeat=1,
        run_scenario=_runner(fail_at_level=None), make_params=_params, step=10,
        on_level=lambda lr: seen.append(lr.level))
    assert seen == [1, 10, 100, 1000]                 # ×10 escalation, reaches cap exactly
    assert bp is None


def test_run_uses_step_for_per_axis():
    levels, _ = escalation.run(
        {"linear": {"file_count": 100, "depth": 8}}, repeat=1,
        run_scenario=_runner(fail_at_level=None), make_params=_params,
        step_for=lambda axis: 10 if axis == "file_count" else 2)
    by_axis = {}
    for lv in levels:
        by_axis.setdefault(lv.axis, []).append(lv.level)
    assert by_axis["file_count"] == [1, 10, 100]       # decade
    assert by_axis["depth"] == [1, 2, 4, 8]            # binary


def test_run_sweeps_all_topology_axes():
    topology_axes = {"linear": {"depth": 2, "feeds": 2}, "diamond": {"branches": 2}}
    levels, breaking = escalation.run(
        topology_axes, repeat=2, run_scenario=_runner(fail_at_level=None),
        make_params=_params,
    )
    # 3 axes, each escalating [1, 2] => 6 level results, no breaking points
    assert len(levels) == 6
    assert breaking == []
