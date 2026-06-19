"""
Tests for benchmarks.recovery — health and quiescence waits.
"""

from benchmarks.recovery import wait_for_health, wait_for_quiescence


class FlippingApi:
    """
    health() returns False for the first ``healthy_after`` calls, then True.
    """

    def __init__(self, healthy_after):
        self.healthy_after = healthy_after
        self.calls = 0

    def health(self):
        self.calls += 1
        return self.calls > self.healthy_after


# -- wait_for_health -------------------------------------------------------------------

def test_wait_for_health_returns_when_healthy():
    assert wait_for_health(FlippingApi(2), timeout=1.0, interval=0.001)


def test_wait_for_health_times_out():
    assert not wait_for_health(FlippingApi(10_000), timeout=0.02, interval=0.001)


# -- wait_for_quiescence ---------------------------------------------------------------

def test_quiescence_waits_until_counts_drop():
    seq = iter([{"feeds": 5, "instances": 9},
                {"feeds": 3, "instances": 6},
                {"feeds": 2, "instances": 3}])
    before = {"feeds": 2, "instances": 3}
    assert wait_for_quiescence(lambda: next(seq), before, timeout_s=1.0,
                               interval_s=0.001)


def test_quiescence_times_out_when_counts_stay_high():
    before = {"feeds": 2, "instances": 3}
    assert not wait_for_quiescence(lambda: {"feeds": 5, "instances": 9}, before,
                                   timeout_s=0.01, interval_s=0.001)


def test_quiescence_checks_at_least_once_even_with_zero_timeout():
    before = {"feeds": 2, "instances": 3}
    assert wait_for_quiescence(lambda: {"feeds": 2, "instances": 3}, before,
                               timeout_s=0.0, interval_s=0.001)
