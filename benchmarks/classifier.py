"""
Scenario classification policy (pure).

Maps observed facts (``PollResult`` + RED rollup) to a PASS / DEGRADED / FAIL verdict
per the strategy's failure criteria (§10). The distinction matters: hard failures stop
an axis and mark the breaking point, whereas SLO breaches are recorded as DEGRADED and
escalation continues — so the sweep keeps pushing toward the real wall.
"""

from __future__ import annotations

from .config import Thresholds
from .models import Classification, PollResult, Verdict


def classify(poll: PollResult, red: dict, thresholds: Thresholds) -> Classification:
    hard: list[str] = []

    if poll.hard_failures:
        hard.extend(poll.hard_failures)

    if red.get("status_5xx", 0) > 0:
        hard.append(f"api_5xx:{red['status_5xx']}")

    if red.get("timeouts", 0) > 0:
        hard.append(f"api_timeout:{red['timeouts']}")

    if poll.timed_out:
        hard.append("scenario_timeout")

    if poll.no_progress:
        hard.append("no_progress")

    if not poll.terminal and not (poll.timed_out or poll.no_progress):
        # defensive: stopped polling without a terminal state or a known reason
        hard.append("not_terminal")

    if hard:
        return Classification(Verdict.FAIL, tuple(hard))

    degraded: list[str] = []
    p95 = _workload_p95(red)

    if p95 > thresholds.api_p95_latency_ms:
        degraded.append(f"p95_latency:{p95:.0f}ms>{thresholds.api_p95_latency_ms}ms")

    if degraded:
        return Classification(Verdict.DEGRADED, tuple(degraded))
    
    return Classification(Verdict.PASS)


def _workload_p95(red: dict) -> float:
    """
    Worst p95 across workload endpoint classes (poll traffic already excluded).
    """
    by_class = red.get("by_class", {})
    return max((c.get("p95_ms", 0.0) for c in by_class.values()), default=0.0)
