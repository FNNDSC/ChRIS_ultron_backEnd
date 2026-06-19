from benchmarks.metrics import (instance_makespan, max_concurrent_active, percentile,
                                phase_durations, red_rollup, resource_rollup,
                                timelines_rollup)
from benchmarks.models import (PluginRole, RequestRecord, ResourceSample, StatusTimeline)


def test_percentile_basic():
    assert percentile([], 95) == 0.0
    assert percentile([5], 95) == 5
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([1, 2, 3, 4], 100) == 4


def _req(cls, ms, ok=True, code=200, t=0.0):
    return RequestRecord(endpoint_class=cls, method="POST", status_code=code,
                         latency_ms=ms, ok=ok, t=t)


def test_red_rollup_excludes_poll_and_counts_errors():
    records = [
        _req("create", 100, t=0.0),
        _req("create", 300, t=1.0),
        _req("create", 0, ok=False, code=500, t=2.0),
        _req("poll", 9999, t=2.0),          # excluded from workload view
    ]
    red = red_rollup(records)
    assert "poll" not in red["by_class"]
    assert red["by_class"]["create"]["count"] == 3
    assert red["status_5xx"] == 1
    assert red["errors"] == 1
    assert red["total_requests"] == 3


def test_red_rollup_counts_timeouts_as_zero_status():
    red = red_rollup([_req("list", 30000, ok=False, code=0, t=0.0)])
    assert red["timeouts"] == 1


def _timeline(inst, **first_seen):
    tl = StatusTimeline(instance_id=inst, node_key=f"n{inst}", role=PluginRole.DS)
    for status, t in first_seen.items():
        tl.observe(status, t)
    return tl


def test_phase_durations_and_makespan():
    tl = _timeline(1, created=0, waiting=1, scheduled=2, started=3,
                   registeringFiles=5, finishedSuccessfully=8)
    durations = phase_durations(tl)
    assert durations["created"] == 1
    assert durations["started"] == 2          # started(3) -> registeringFiles(5)
    assert durations["registeringFiles"] == 3  # -> terminal(8)
    assert instance_makespan(tl) == 8


def test_observe_records_first_seen_only():
    tl = _timeline(1)
    tl.observe("started", 3.0)
    tl.observe("started", 9.0)                  # later sighting ignored for first_seen
    assert tl.first_seen["started"] == 3.0
    assert tl.final_status == "started"


def test_timelines_rollup_counts_and_concurrency():
    tls = [
        _timeline(1, created=0, started=1, finishedSuccessfully=4),
        _timeline(2, created=0, started=1, finishedWithError=3),
    ]
    roll = timelines_rollup(tls)
    assert roll["instances"] == 2
    assert roll["final_status_counts"]["finishedSuccessfully"] == 1
    assert roll["final_status_counts"]["finishedWithError"] == 1
    assert roll["completed"] == 2


def test_max_concurrent_active():
    # both active over [0,4] and [0,3] -> peak concurrency 2
    tls = [
        _timeline(1, created=0.0, finishedSuccessfully=4.0),
        _timeline(2, created=0.0, finishedSuccessfully=3.0),
    ]
    assert max_concurrent_active(tls) == 2


def test_resource_rollup_peaks():
    samples = [
        ResourceSample(t=0, container="db", kind="service", cpu_pct=10, mem_bytes=100,
                       mem_limit_bytes=1000),
        ResourceSample(t=1, container="db", kind="service", cpu_pct=80, mem_bytes=500,
                       mem_limit_bytes=1000),
    ]
    roll = resource_rollup(samples)
    assert roll["db"]["cpu_pct_peak"] == 80
    assert roll["db"]["mem_bytes_peak"] == 500
    assert roll["db"]["samples"] == 2


def test_resource_rollup_blkio_delta_and_pids_peak():
    # blkio counters are cumulative since container start -> rollup reports the delta
    samples = [
        ResourceSample(t=0, container="db", kind="service", cpu_pct=1, mem_bytes=1,
                       mem_limit_bytes=10, blkio_read_bytes=1000,
                       blkio_write_bytes=5000, pids=3),
        ResourceSample(t=1, container="db", kind="service", cpu_pct=1, mem_bytes=1,
                       mem_limit_bytes=10, blkio_read_bytes=1500,
                       blkio_write_bytes=9000, pids=7),
    ]
    roll = resource_rollup(samples)
    assert roll["db"]["blkio_read_bytes"] == 500
    assert roll["db"]["blkio_write_bytes"] == 4000
    assert roll["db"]["pids_peak"] == 7


def test_timelines_rollup_throughput_and_littles_law():
    # two instances, each in-system for 10s over a 10s span -> 0.2/s, ~2 in flight
    tls = [
        _timeline(1, created=0, finishedSuccessfully=10),
        _timeline(2, created=0, finishedSuccessfully=10),
    ]
    roll = timelines_rollup(tls)
    assert roll["throughput_per_s"] == 0.2
    assert roll["littles_law_avg_inflight"] == 2.0
    assert roll["max_concurrent_active"] == 2
