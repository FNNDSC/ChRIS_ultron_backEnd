"""
The OFAT (one-factor-at-a-time) escalation engine (pure control flow).

For each topology/axis it runs the scenario at levels 1, 2, 4, 8 ... up to a cap,
repeating ``repeat`` times per level, until a hard failure marks the breaking point.
Repeats short-circuit on the first hard failure: re-running an already-failing level
would hammer a broken stack before recovery gets a chance, and at full-tier timeouts
each extra repeat can cost an hour of wall clock.

All side effects are injected: ``run_scenario`` actually runs a scenario, ``make_params``
maps (topology, axis, level, repeat) to a ``ScenarioParams``, and the optional
``on_level`` / ``on_fail`` hooks let the runner persist results and recover. This keeps
the engine trivially unit-testable with a fake ``run_scenario``.
"""

from __future__ import annotations

from typing import Callable, Optional

from .models import (BreakingPoint, LevelResult, ScenarioParams, ScenarioResult,
                     Verdict)


RunScenario = Callable[[ScenarioParams], ScenarioResult]

MakeParams = Callable[[str, str, int, int], ScenarioParams]

LevelHook = Callable[[LevelResult], None]

StepFor = Callable[[str], int]

_WORST_FIRST = (Verdict.FAIL, Verdict.DEGRADED, Verdict.PASS)


def aggregate_verdict(repeats: list[ScenarioResult]) -> tuple[Verdict, tuple[str, ...]]:
    """
    Worst-of across repeats; criteria unioned from the repeats at that verdict.
    """
    verdicts = {r.classification.verdict for r in repeats}
    worst = next(v for v in _WORST_FIRST if v in verdicts)
    criteria: list[str] = []

    for r in repeats:
        if r.classification.verdict is worst:
            for c in r.classification.criteria:
                if c not in criteria:
                    criteria.append(c)
    
    return worst, tuple(criteria)


def escalate_axis(topology: str, axis: str, cap: int, repeat: int,
                  run_scenario: RunScenario, make_params: MakeParams,
                  on_level: Optional[LevelHook] = None,
                  on_fail: Optional[LevelHook] = None,
                  step: int = 2,
                  ) -> tuple[list[LevelResult], Optional[BreakingPoint]]:
    
    levels: list[LevelResult] = []
    level = 1

    while level <= cap:
        repeats: list[ScenarioResult] = []

        for i in range(repeat):
            repeats.append(run_scenario(make_params(topology, axis, level, i)))
  
            if repeats[-1].classification.verdict is Verdict.FAIL:
                break                   # short-circuit: don't hammer a failing system
        
        verdict, criteria = aggregate_verdict(repeats)
        result = LevelResult(topology, axis, level, verdict, criteria, repeats)
        levels.append(result)

        if on_level:
            on_level(result)

        if verdict is Verdict.FAIL:
            if on_fail:
                on_fail(result)

            return levels, BreakingPoint(topology, axis, level, criteria)
        
        level *= step
    return levels, None


def run(topology_axes: dict[str, dict[str, int]], repeat: int,
        run_scenario: RunScenario, make_params: MakeParams,
        on_level: Optional[LevelHook] = None,
        on_fail: Optional[LevelHook] = None,
        step_for: Optional[StepFor] = None,
        ) -> tuple[list[LevelResult], list[BreakingPoint]]:
    """
    Sweep every (topology, axis) in the tier, collecting levels and breaking points.

    ``step_for(axis)`` selects the escalation multiplier per axis (binary ×2 by default;
    ``file_count`` escalates by decade ×10 — see ``config.step_for``).
    """
    step_for = step_for or (lambda axis: 2)
    all_levels: list[LevelResult] = []
    breaking: list[BreakingPoint] = []

    for topology, axes in topology_axes.items():
        for axis, cap in axes.items():
            levels, bp = escalate_axis(topology, axis, cap, repeat, run_scenario,
                                       make_params, on_level, on_fail,
                                       step=step_for(axis))
            all_levels.extend(levels)

            if bp is not None:
                breaking.append(bp)
                
    return all_levels, breaking
