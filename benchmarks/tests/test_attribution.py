"""
Tests for the bottleneck-attribution instrumentation: broker queue depths and
pg_stat_statements snapshots.
"""

from benchmarks.broker import BrokerClient, encode_command, parse_reply
from benchmarks.metrics import MetricSink, queue_rollup
from benchmarks.models import QueueSample
from benchmarks.pg_stats import parse_psql_rows
from benchmarks.stats_sampler import StatsSampler


# -- RESP framing ------------------------------------------------------------------------

def test_encode_command_resp_framing():
    assert encode_command("LLEN", "main1") == b"*2\r\n$4\r\nLLEN\r\n$5\r\nmain1\r\n"


def test_parse_reply_integer_and_simple_string():
    assert parse_reply(b":42\r\n") == 42
    assert parse_reply(b"+PONG\r\n") == "PONG"


def test_parse_reply_rejects_errors():
    import pytest
    with pytest.raises(ValueError):
        parse_reply(b"-ERR unknown command\r\n")


def test_broker_unreachable_degrades_to_empty():
    client = BrokerClient("127.0.0.1", 1, timeout=0.1)   # nothing listens on port 1
    assert not client.available
    assert client.depths() == {}


class FakeBroker:
    available = True

    def __init__(self, depths):
        self._depths = depths

    def depths(self):
        return dict(self._depths)


def test_sampler_records_queue_depths():
    class NoDocker:
        def service_containers(self):
            return []

        def job_containers(self):
            return []

    sink = MetricSink()
    sampler = StatsSampler(NoDocker(), sink, broker=FakeBroker({"main2": 7}))
    sampler._sample_once()
    samples = sink.queues()
    assert len(samples) == 1
    assert samples[0].queue == "main2" and samples[0].depth == 7


def test_queue_rollup_peak_and_mean():
    samples = [QueueSample(0, "main2", 0), QueueSample(1, "main2", 10),
               QueueSample(2, "main2", 4), QueueSample(0, "periodic", 1)]
    roll = queue_rollup(samples)
    assert roll["main2"] == {"depth_peak": 10, "depth_mean": 4.7, "samples": 3}
    assert roll["periodic"]["depth_peak"] == 1


# -- psql output parsing -------------------------------------------------------------------

def test_parse_psql_rows_types_and_shape():
    out = "120\t4521\t37.67\t2400\tSELECT * FROM plugininstances_plugininstance\n" \
          "3\t12\t4.0\t3\tUPDATE feeds_feed SET name = $1\n" \
          "malformed line without tabs\n"
    rows = parse_psql_rows(out, ("calls", "total_ms", "mean_ms", "rows", "query"))
    assert len(rows) == 2
    assert rows[0]["calls"] == 120 and rows[0]["mean_ms"] == 37.67
    assert rows[0]["query"].startswith("SELECT * FROM")
