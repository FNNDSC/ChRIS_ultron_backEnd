from benchmarks.classifier import classify
from benchmarks.config import Thresholds
from benchmarks.models import PollResult, Verdict

THRESHOLDS = Thresholds(
    healthcheck_timeout_s=30, api_request_timeout_s=30, api_p95_latency_ms=2000,
    no_progress_timeout_s=300, scenario_timeout_s=1200,
)


def _poll(**kw):
    base = dict(timelines=[], makespan_s=1.0, terminal=True, hard_failures=(),
                no_progress=False, timed_out=False, final_status_counts={})
    base.update(kw)
    return PollResult(**base)


def _red(**kw):
    base = dict(by_class={"create": {"p95_ms": 100.0}}, total_requests=10, errors=0,
                status_5xx=0, timeouts=0, requests_per_s=5.0)
    base.update(kw)
    return base


def test_clean_run_passes():
    assert classify(_poll(), _red(), THRESHOLDS).verdict is Verdict.PASS


def test_instance_error_is_hard_fail():
    c = classify(_poll(hard_failures=("finishedWithError:inst-7",)), _red(), THRESHOLDS)
    assert c.verdict is Verdict.FAIL
    assert "finishedWithError:inst-7" in c.criteria


def test_5xx_is_hard_fail():
    c = classify(_poll(), _red(status_5xx=2), THRESHOLDS)
    assert c.verdict is Verdict.FAIL
    assert any("api_5xx" in x for x in c.criteria)


def test_timeout_and_no_progress_are_hard_fail():
    assert classify(_poll(timed_out=True), _red(), THRESHOLDS).verdict is Verdict.FAIL
    assert classify(_poll(terminal=False, no_progress=True), _red(),
                    THRESHOLDS).verdict is Verdict.FAIL


def test_p95_breach_is_degraded_not_fail():
    red = _red(by_class={"create": {"p95_ms": 5000.0}})
    c = classify(_poll(), red, THRESHOLDS)
    assert c.verdict is Verdict.DEGRADED
    assert any("p95_latency" in x for x in c.criteria)


def test_hard_failure_takes_precedence_over_degraded():
    red = _red(by_class={"create": {"p95_ms": 9000.0}}, status_5xx=1)
    assert classify(_poll(), red, THRESHOLDS).verdict is Verdict.FAIL


def test_not_terminal_without_known_reason_is_hard_fail():
    # defensive branch: polling stopped without a terminal state, timeout or stall
    c = classify(_poll(terminal=False), _red(), THRESHOLDS)
    assert c.verdict is Verdict.FAIL
    assert "not_terminal" in c.criteria
