"""
Tests for benchmarks.recovery — health and quiescence waits, and API recovery after a
Locust step.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from benchmarks import recovery
from benchmarks.recovery import (all_ok, api_recovery, http_burst, parse_pool_stats,
                                 probe_recovery, wait_for_health, wait_for_quiescence)


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


# -- API recovery after a Locust step -------------------------------------------------------

class FakeClock:
    """
    A clock that only moves when someone sleeps, or when a burst takes ``burst_s``.
    """

    def __init__(self, burst_s=0.5):
        self.now = 1000.0
        self.burst_s = burst_s

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def bursts(clock, *statuses):
    """
    A probe that returns the given bursts in turn (the last one forever).
    """
    seq = list(statuses)

    def probe():
        clock.now += clock.burst_s
        return seq.pop(0) if len(seq) > 1 else seq[0]
    return probe


def pool(pid, checked_out):
    return {pid: {"pid": pid, "checked_out": checked_out}}


def test_all_ok_needs_a_burst_of_2xx():
    assert all_ok([200, 204])
    assert not all_ok([200, 500]) and not all_ok([200, None]) and not all_ok([])


def test_probe_recovery_passes_on_a_healthy_first_burst():
    clock = FakeClock()
    result = probe_recovery(bursts(clock, [200] * 4), window_s=60, clock=clock,
                            sleep=clock.sleep)

    assert result["recovered"] and result["seconds"] == 0.0
    assert result["rounds"] == [{"t": 0.0, "statuses": {"200": 4}, "ok": True}]


def test_probe_recovery_waits_for_every_request_of_a_burst():
    clock = FakeClock()
    result = probe_recovery(bursts(clock, [500, 200], [500, 200], [200, 200]),
                            window_s=60, interval_s=5, clock=clock, sleep=clock.sleep)

    assert result["recovered"] and result["seconds"] == 11.0   # two failed rounds
    assert [r["ok"] for r in result["rounds"]] == [False, False, True]


def test_probe_recovery_gives_up_after_the_window():
    clock = FakeClock()
    result = probe_recovery(bursts(clock, [500]), window_s=20, interval_s=5, clock=clock,
                            sleep=clock.sleep)

    assert not result["recovered"] and result["seconds"] is None
    assert len(result["rounds"]) == 5        # rounds at 0, 5.5, 11, 16.5 and 22 s


def test_probe_recovery_needs_every_pool_back_after_the_burst():
    clock = FakeClock()
    seen = []
    states = [{**pool(1, 0), **pool(2, 10)}, {**pool(1, 0), **pool(2, 0)}]

    def pools(since):
        seen.append(since)
        return states.pop(0)

    result = probe_recovery(bursts(clock, [200]), window_s=60, interval_s=5, pools=pools,
                            settle_s=6, clock=clock, sleep=clock.sleep)

    assert result["recovered"]
    assert result["rounds"][0]["checked_out"] == {"1": 0, "2": 10}
    assert not result["rounds"][0]["ok"] and result["rounds"][1]["ok"]
    # each round reads only what the workers logged after its burst ended
    assert seen == [1000.5, 1000.5 + 6 + 5 + 0.5]


def test_probe_recovery_records_the_pools_of_a_failed_round():
    clock = FakeClock()
    seen = []

    def pools(since):
        seen.append(since)
        return {**pool(1, 10), **pool(2, 0)}

    result = probe_recovery(bursts(clock, [500, 200]), window_s=0, pools=pools,
                            settle_s=6, clock=clock, sleep=clock.sleep)

    assert not result["recovered"]
    assert result["rounds"][0]["checked_out"] == {"1": 10, "2": 0}
    assert seen == [1000.0]                  # logged since the round started, no settling


def test_probe_recovery_needs_every_worker_to_report():
    clock = FakeClock()
    result = probe_recovery(bursts(clock, [200]), window_s=10, interval_s=5,
                            pools=lambda since: {**pool(1, 0), **pool(2, 0)}, workers=4,
                            clock=clock, sleep=clock.sleep)

    assert not result["recovered"]


def test_parse_pool_stats_keeps_the_latest_line_of_each_worker():
    log = "\n".join([
        '[INFO][core.utils] db_pool_stats {"pid": 9, "checked_out": 10}',
        "INFO:     172.18.0.9:4242 - \"GET /api/v1/ HTTP/1.1\" 200 OK",
        '[INFO][core.utils] db_pool_stats {"pid": 10, "checked_out": 0}',
        '[INFO][core.utils] db_pool_stats {"pid": 9, "checked_out": 0}',
        "[INFO][core.utils] db_pool_stats {not json}",
    ])

    assert parse_pool_stats(log) == {9: {"pid": 9, "checked_out": 0},
                                     10: {"pid": 10, "checked_out": 0}}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.headers.get("Accept") else 400)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_http_burst_reports_each_request():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        assert http_burst(url, 4, timeout=5) == [200] * 4
    finally:
        server.shutdown()
        server.server_close()
    assert http_burst(url, 2, timeout=1) == [None, None]       # nothing listening now


class FakeChrisDocker:
    def __init__(self, log):
        self.log = log
        self.since = []

    def find_service(self, service):
        return service

    def logs(self, container, tail=200, since=None):
        self.since.append(since)
        return self.log


def test_api_recovery_checks_the_pools_when_workers_log_them(monkeypatch):
    monkeypatch.setattr(recovery, "probe_api", lambda base_url: [200] * 16)
    monkeypatch.setattr(recovery, "connection_states",
                        lambda docker: [{"client_addr": "10.0.0.2", "state": "idle",
                                         "count": 20}])
    monkeypatch.setattr(recovery.time, "sleep", lambda seconds: None)
    docker = FakeChrisDocker("\n".join(
        f"db_pool_stats {json.dumps({'pid': pid, 'checked_out': 0})}" for pid in (1, 2)))

    result = api_recovery("http://chris:8000/api/v1/", docker, window_s=60,
                          stats_interval_s=5, workers=2)

    assert result["recovered"] and result["pools_checked"]
    assert result["connections"][0]["count"] == 20
    assert docker.since and docker.since[0] is not None


def test_api_recovery_without_pool_stats_relies_on_the_bursts(monkeypatch):
    monkeypatch.setattr(recovery, "probe_api", lambda base_url: [200] * 16)
    monkeypatch.setattr(recovery, "connection_states", lambda docker: [])
    docker = FakeChrisDocker("")

    result = api_recovery("http://chris:8000/api/v1/", docker, window_s=60)

    assert result["recovered"] and not result["pools_checked"]
    assert docker.since == []
