"""
Tests for the bottleneck-attribution instrumentation: broker queue depths,
pg_stat_statements snapshots, pg_stat_activity connection states, the Postgres server's
settings and cumulative counters, the db container's cgroup counters, and the environment
manifest that records the settings.
"""

import json
import os
from types import SimpleNamespace

import pytest

from benchmarks.broker import BrokerClient, encode_command, parse_reply
from benchmarks.docker_client import (CGROUP_COUNTERS_CMD, CONTAINER_START_KEY, DockerClient,
                                      parse_cgroup_counters)
from benchmarks.environment import ENVELOPE_KEYS, POSTGRES_SETTINGS, collect_environment
from benchmarks.metrics import MetricSink, queue_rollup
from benchmarks.models import QueueSample
from benchmarks.pg_stats import (PgStatStatements, connection_states, counter_delta,
                                 counter_windows, max_deltas, parse_psql_rows,
                                 server_counters, server_counters_error, server_settings,
                                 settings_sql)
from benchmarks.stats_sampler import StatsSampler


# -- RESP framing ------------------------------------------------------------------------

def test_encode_command_resp_framing():
    assert encode_command("LLEN", "main1") == b"*2\r\n$4\r\nLLEN\r\n$5\r\nmain1\r\n"


def test_parse_reply_integer_and_simple_string():
    assert parse_reply(b":42\r\n") == 42
    assert parse_reply(b"+PONG\r\n") == "PONG"


def test_parse_reply_rejects_errors():
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


class FakeDbDocker:
    """Records the SQL each ``psql`` call runs and answers with one statement row."""

    def __init__(self):
        self.sql = []

    def service_env(self, service):
        return {"POSTGRES_USER": "chris", "POSTGRES_DB": "chris_dev"}

    def exec_in_service(self, service, cmd):
        self.sql.append(cmd[-1])
        return 0, "3\t12\t4.0\t3\tUPDATE feeds_feed SET name = $1\n"


def test_snapshot_keeps_every_statement_by_default():
    docker = FakeDbDocker()
    rows = PgStatStatements(docker).snapshot()

    assert "LIMIT" not in docker.sql[-1]  # nosec B101 - pytest assertion
    assert docker.sql[-1].rstrip().endswith("ORDER BY total_exec_time DESC")  # nosec B101 - pytest assertion
    assert rows[0]["query"] == "UPDATE feeds_feed SET name = $1"  # nosec B101 - pytest assertion


def test_snapshot_limit_is_optional():
    docker = FakeDbDocker()
    PgStatStatements(docker).snapshot(limit=15)

    assert docker.sql[-1].endswith("ORDER BY total_exec_time DESC LIMIT 15")  # nosec B101 - pytest assertion


def test_connection_states_counts_connections_by_client_and_state():
    class ActivityDocker(FakeDbDocker):
        def exec_in_service(self, service, cmd):
            self.sql.append(cmd[-1])
            return 0, "172.18.0.7\tidle\t40\nlocal\tactive\t1\n"

    docker = ActivityDocker()
    rows = connection_states(docker)

    expected = [{"client_addr": "172.18.0.7", "state": "idle", "count": 40},
                {"client_addr": "local", "state": "active", "count": 1}]

    assert "pg_stat_activity" in docker.sql[-1]  # nosec B101 - pytest assertion
    assert rows == expected  # nosec B101 - pytest assertion


def test_connection_states_is_empty_when_psql_cannot_run():
    class DownDocker(FakeDbDocker):
        def exec_in_service(self, service, cmd):
            return -1, "service 'db' not running"

    assert connection_states(DownDocker()) == []  # nosec B101 - pytest assertion


# -- server settings and counters ------------------------------------------------------------

class JsonDocker(FakeDbDocker):
    """Answers every psql call with one JSON document, after a line of psql's stderr."""

    def __init__(self, doc, code=0):
        super().__init__()
        self.doc = doc
        self.code = code

    def exec_in_service(self, service, cmd):
        self.sql.append(cmd[-1])
        return self.code, "WARNING:  some notice\n" + json.dumps(self.doc) + "\n"


SETTINGS_DOC = {"settings": {"random_page_cost": "1.1", "max_wal_size": "8GB",
                             "DateStyle": "ISO, MDY"},
                "key_settings": ["max_wal_size", "random_page_cost"],
                "altered": None,
                "table_options": {"core_chrisfile": ["autovacuum_vacuum_scale_factor=0.02"]}}


def test_server_settings_keeps_values_as_text():
    docker = JsonDocker(SETTINGS_DOC)
    recorded = server_settings(docker, ("random_page_cost", "it's"))

    # strings, so archived runs compare as text; no ALTER SYSTEM override -> []
    assert recorded["settings"]["random_page_cost"] == "1.1"  # nosec B101 - pytest assertion
    assert recorded["key_settings"] == [  # nosec B101 - pytest assertion
        "max_wal_size", "random_page_cost"]
    assert recorded["altered"] == []  # nosec B101 - pytest assertion
    assert recorded["table_options"]["core_chrisfile"] == [  # nosec B101 - pytest assertion
        "autovacuum_vacuum_scale_factor=0.02"]
    assert "'it''s'" in docker.sql[-1]  # nosec B101 - pytest assertion
    assert "'core_chrisfile'" in docker.sql[-1]  # nosec B101 - pytest assertion


def test_settings_sql_records_every_setting_and_only_overrides_in_effect():
    sql = settings_sql(("work_mem",))

    # every setting, so a run on another configuration file still has every name
    every_setting = "current_setting(name) ORDER BY name) FROM pg_settings)"
    assert every_setting in sql  # nosec B101 - pytest assertion
    # pg_file_settings would also list ALTER SYSTEM lines that -c overrides or that
    # await a reload; pg_settings.sourcefile names only the file a value came from
    assert "pg_file_settings" not in sql  # nosec B101 - pytest assertion
    assert "sourcefile LIKE '%/postgresql.auto.conf'" in sql  # nosec B101 - pytest assertion


def test_server_settings_is_empty_when_psql_fails_or_prints_no_json():
    failing = JsonDocker(SETTINGS_DOC, code=2)
    assert server_settings(failing, ("x",)) == {}  # nosec B101 - pytest assertion

    class GarbageDocker(FakeDbDocker):
        def exec_in_service(self, service, cmd):
            return 0, "not json"

    assert server_settings(GarbageDocker(), ("x",)) == {}  # nosec B101 - pytest assertion


def test_server_counters_returns_the_snapshot_or_nothing():
    doc = {"at": 10.0, "num_requested": 1, "checkpointer_reset": "t0"}
    docker = JsonDocker(doc)

    assert server_counters(docker) == doc  # nosec B101 - pytest assertion
    assert "pg_stat_checkpointer" in docker.sql[-1]  # nosec B101 - pytest assertion
    # spaces in a process type become underscores, so the key passes through a shell
    assert "replace(backend_type, ' ', '_')" in docker.sql[-1]  # nosec B101 - pytest assertion
    assert server_counters(JsonDocker(doc, code=1)) == {}  # nosec B101 - pytest assertion


def test_server_counters_error_says_why_the_counters_read_nothing():
    class TooMany(FakeDbDocker):
        def exec_in_service(self, service, cmd):
            return 2, "psql: error: FATAL:  sorry, too many clients already\n"

    assert server_counters_error(JsonDocker({"at": 1.0})) is None  # nosec B101 - pytest assertion
    assert "too many clients" in server_counters_error(TooMany())  # nosec B101 - pytest assertion


def _snap(at, **counters):
    return {"at": at, "checkpointer_reset": "t0", "wal_reset": "t0", "server_start": "s0",
            **counters}


def test_counter_delta_subtracts_counters_and_times_the_window():
    before = _snap(100.0, num_requested=1, wal_bytes=1000, checkpoint_write_ms=1.25)
    after = _snap(160.5, num_requested=1, wal_bytes=4000, checkpoint_write_ms=3.5,
                  **{"io_write_bytes:relation:client_backend": 8192})
    delta = counter_delta(before, after)

    assert delta["num_requested"] == 0  # nosec B101 - pytest assertion
    assert delta["wal_bytes"] == 3000  # nosec B101 - pytest assertion
    assert delta["checkpoint_write_ms"] == 2.2  # nosec B101 - pytest assertion
    # a per-process-type counter that first appears counts from 0
    assert delta["io_write_bytes:relation:client_backend"] == 8192  # nosec B101 - pytest assertion
    assert delta["seconds"] == 60.5  # nosec B101 - pytest assertion
    assert "checkpointer_reset" not in delta  # nosec B101 - pytest assertion
    assert "reset" not in delta  # nosec B101 - pytest assertion


def test_a_postgres_crash_resets_its_counters_but_keeps_the_containers():
    # the kernel OOM-kills a backend: Postgres crash-restarts and zeroes its statistics,
    # yet num_requested can read 1 -> 1; the container and its counters keep going
    before = _snap(0.0, num_requested=1, wal_bytes=5000, cgroup_oom_kill=0,
                   cgroup_write_bytes=100)
    after = dict(_snap(9.0, num_requested=1, wal_bytes=7000, cgroup_oom_kill=1,
                       cgroup_write_bytes=300), checkpointer_reset="t1")

    assert counter_delta(before, after) == {  # nosec B101 - pytest assertion
        "reset": True, "cgroup_oom_kill": 1, "cgroup_write_bytes": 200, "seconds": 9.0}


def test_a_postgres_counter_going_down_is_a_reset():
    delta = counter_delta(_snap(0.0, wal_bytes=5000), _snap(9.0, wal_bytes=10))

    assert delta == {"reset": True, "seconds": 9.0}  # nosec B101 - pytest assertion


def test_a_cgroup_counter_going_down_leaves_the_cgroup_counters_out():
    delta = counter_delta(_snap(0.0, wal_bytes=10, cgroup_write_bytes=10_000),
                          _snap(9.0, wal_bytes=30, cgroup_write_bytes=500))

    assert delta == {"wal_bytes": 20, "seconds": 9.0}  # nosec B101 - pytest assertion


def test_a_server_restart_invalidates_both_kinds_of_counter():
    # a clean restart keeps Postgres's statistics but restarts the container's cgroup
    # counters, which may already have climbed past their earlier value
    before = _snap(0.0, num_requested=1, cgroup_write_bytes=1000)
    after = dict(_snap(9.0, num_requested=2, cgroup_write_bytes=5000), server_start="s1")

    delta = counter_delta(before, after)
    assert delta == {"reset": True, "seconds": 9.0}  # nosec B101 - pytest assertion


def test_counter_delta_marks_postgres_unreadable_and_keeps_the_containers():
    # psql failed at the window's start (crash recovery, say): Postgres's counters are
    # unknown, not zero; the container's counters still have a delta
    before = {"cgroup_write_bytes": 100, "cgroup_oom_kill": 0, CONTAINER_START_KEY: "c0"}
    after = _snap(9.0, wal_bytes=7000, cgroup_write_bytes=400, cgroup_oom_kill=1,
                  **{"io_write_bytes:wal:client_backend": 4096, CONTAINER_START_KEY: "c0"})

    assert counter_delta(before, after) == {  # nosec B101 - pytest assertion
        "unreadable": True, "cgroup_write_bytes": 300, "cgroup_oom_kill": 1}


def test_a_container_restart_drops_its_counters_even_with_postgres_unreadable():
    # without server_start at both ends, the container's own start time tells
    before = {"cgroup_write_bytes": 100, CONTAINER_START_KEY: "c0"}
    after = {"cgroup_write_bytes": 900, CONTAINER_START_KEY: "c1"}

    assert counter_delta(before, after) == {"unreadable": True}  # nosec B101 - pytest assertion


def test_counter_delta_leaves_out_a_counter_the_earlier_snapshot_missed():
    # the cgroup read failed at the window's start: no delta rather than the container's
    # whole history since it started
    delta = counter_delta(_snap(0.0, wal_bytes=10), _snap(5.0, wal_bytes=30,
                                                          cgroup_write_bytes=9_000_000))

    assert delta == {"wal_bytes": 20, "seconds": 5.0}  # nosec B101 - pytest assertion


def test_counter_delta_needs_both_snapshots():
    assert counter_delta({}, _snap(1.0)) is None  # nosec B101 - pytest assertion
    assert counter_delta(_snap(1.0), {}) is None  # nosec B101 - pytest assertion


def test_counter_windows_split_workload_and_cleanup():
    start, mid, end = _snap(0.0, temp_bytes=0), _snap(5.0, temp_bytes=10), _snap(8.0, temp_bytes=40)
    windows = counter_windows(start, mid, end)

    assert windows["workload"]["temp_bytes"] == 10  # nosec B101 - pytest assertion
    assert windows["cleanup"]["temp_bytes"] == 30  # nosec B101 - pytest assertion
    assert windows["snapshots"]["cleanup_end"] is end  # nosec B101 - pytest assertion
    # a scenario that keeps its feeds has no cleanup window
    assert counter_windows(start, mid, None)["cleanup"] is None  # nosec B101 - pytest assertion


def test_max_deltas_takes_each_counters_largest_value():
    merged = max_deltas([{"num_requested": 2, "seconds": 10.0},
                         {"num_requested": 0, "wal_bytes": 900, "seconds": 30.0}])

    # per counter, so one result can mix windows; a counter in one window only is kept
    assert merged == {  # nosec B101 - pytest assertion
        "num_requested": 2, "wal_bytes": 900, "seconds": 30.0}


def test_container_start_known_at_one_end_only_is_no_restart():
    # the cgroup read failed at the start: no identity to compare, so no restart, and
    # the counters the earlier snapshot lacks have no delta
    before = _snap(0.0, wal_bytes=10)
    after = _snap(5.0, wal_bytes=30, cgroup_write_bytes=900,
                  **{CONTAINER_START_KEY: "c0"})

    delta = counter_delta(before, after)
    assert delta == {"wal_bytes": 20, "seconds": 5.0}  # nosec B101 - pytest assertion


def test_server_counters_error_on_output_that_is_not_an_object():
    error = server_counters_error(JsonDocker([1, 2]))
    assert error.startswith("unexpected output")  # nosec B101 - pytest assertion


def test_max_deltas_carries_an_unreadable_window():
    merged = max_deltas([{"num_requested": 0, "cgroup_oom_kill": 0},
                         {"unreadable": True, "cgroup_oom_kill": 1}])

    assert merged == {"unreadable": True, "cgroup_oom_kill": 1}  # nosec B101 - pytest assertion


def test_max_deltas_keeps_only_the_container_counters_after_a_reset():
    merged = max_deltas([{"num_requested": 2, "cgroup_oom_kill": 0, "seconds": 5.0},
                         {"reset": True, "cgroup_oom_kill": 1, "seconds": 9.0}])

    assert merged == {  # nosec B101 - pytest assertion
        "reset": True, "cgroup_oom_kill": 1, "seconds": 9.0}


# -- container cgroup counters ---------------------------------------------------------------

def test_parse_cgroup_counters_sums_devices_and_keeps_known_keys():
    text = ("259:0 rbytes=10 wbytes=4096 rios=1 wios=2 dbytes=0 dios=0\n"
            "8:0 rbytes=0 wbytes=1024 rios=0 wios=1 dbytes=0 dios=0\n"
            "pswpin 3\npswpout 7\noom_kill 0\n"
            "grep: /sys/fs/cgroup/memory.events: No such file or directory\n")

    assert parse_cgroup_counters(text) == {  # nosec B101 - pytest assertion
        "cgroup_write_bytes": 5120, "cgroup_pswpin": 3, "cgroup_pswpout": 7,
        "cgroup_oom_kill": 0}
    assert parse_cgroup_counters("sh: cat: not found\n") == {}  # nosec B101 - pytest assertion


def test_parse_cgroup_counters_without_io_stat():
    # cgroup v1, or rootless Podman without the io controller delegated
    text = ("cat: can't open '/sys/fs/cgroup/io.stat': No such file or directory\n"
            "pswpin 0\npswpout 0\noom_kill 2\n")

    assert parse_cgroup_counters(text) == {  # nosec B101 - pytest assertion
        "cgroup_pswpin": 0, "cgroup_pswpout": 0, "cgroup_oom_kill": 2}


def _container(output, code=0, **attrs):
    calls = []

    def exec_run(cmd):
        calls.append(cmd)
        return code, output

    return SimpleNamespace(exec_run=exec_run, calls=calls, labels={}, name="x", attrs=attrs)


def test_cgroup_counters_reads_the_container_and_its_start_time():
    container = _container(b"254:0 rbytes=0 wbytes=2048\noom_kill 1\n",
                           State={"StartedAt": "2026-10-13T19:29:40Z"})
    client = DockerClient.__new__(DockerClient)          # no Docker connection needed
    client.find_service = lambda service: container

    assert client.cgroup_counters("db") == {  # nosec B101 - pytest assertion
        "cgroup_write_bytes": 2048, "cgroup_oom_kill": 1,
        CONTAINER_START_KEY: "2026-10-13T19:29:40Z"}
    assert container.calls == [CGROUP_COUNTERS_CMD]  # nosec B101 - pytest assertion


def test_cgroup_counters_without_a_container_or_its_files_are_empty():
    client = DockerClient.__new__(DockerClient)
    client.find_service = lambda service: None
    assert client.cgroup_counters("db") == {}  # nosec B101 - pytest assertion

    # no counter could be read: no start time on its own either
    client.find_service = lambda service: _container(b"sh: cat: not found\n", code=127,
                                                     State={"StartedAt": "t"})
    assert client.cgroup_counters("db") == {}  # nosec B101 - pytest assertion


def test_service_limits_reads_each_containers_host_config():
    container = SimpleNamespace(
        labels={"com.docker.compose.service": "db"}, name="x-db-1",
        attrs={"HostConfig": {"NanoCpus": 2_000_000_000, "Memory": 4 * 1024 ** 3,
                              "MemorySwap": -1, "ShmSize": 0}})
    client = DockerClient.__new__(DockerClient)
    client.service_containers = lambda: [container]

    assert client.service_limits() == {"db": {  # nosec B101 - pytest assertion
        "cpus": 2.0, "mem_limit": 4 * 1024 ** 3, "memswap_limit": -1, "shm_size": None}}


def test_service_limits_reads_a_cpu_quota_when_nano_cpus_is_unset():
    # Podman can report --cpus 1.5 as a CFS quota over its period
    container = SimpleNamespace(
        labels={"com.docker.compose.service": "db"}, name="x-db-1",
        attrs={"HostConfig": {"NanoCpus": 0, "CpuQuota": 150000, "CpuPeriod": 100000}})
    client = DockerClient.__new__(DockerClient)
    client.service_containers = lambda: [container]

    assert client.service_limits()["db"]["cpus"] == 1.5  # nosec B101 - pytest assertion


# -- environment manifest ----------------------------------------------------------------------

class ManifestDocker(JsonDocker):
    """The Docker calls ``collect_environment`` makes, with one container per service."""

    def info(self):
        return {"NCPU": 16}

    def version(self):
        return {"Version": "29.9.0"}

    def find_service(self, service):
        image = SimpleNamespace(id=f"sha256:{service}", tags=[f"{service}:dev"])
        return SimpleNamespace(image=image)

    def service_limits(self):
        return {"db": {"cpus": 2.0, "mem_limit": 4294967296, "memswap_limit": None,
                       "shm_size": 1073741824}}


def test_collect_environment_records_postgres_settings_limits_and_db_image():
    env = collect_environment(ManifestDocker(SETTINGS_DOC),
                              env={"CUBE_DB_SYNCHRONOUS_COMMIT": "on"})

    assert env["postgres"]["settings"]["max_wal_size"] == "8GB"  # nosec B101 - pytest assertion
    assert env["images"]["db"]["image_id"] == "sha256:db"  # nosec B101 - pytest assertion
    assert env["limits"]["db"]["shm_size"] == 1073741824  # nosec B101 - pytest assertion
    assert env["envelope"]["CUBE_DB_SYNCHRONOUS_COMMIT"] == "on"  # nosec B101 - pytest assertion
    assert set(env["envelope"]) == set(ENVELOPE_KEYS)  # nosec B101 - pytest assertion


# -- against the stack's own Postgres --------------------------------------------------------

def test_the_queries_run_on_the_benchmark_stacks_postgres():
    """
    The SQL and the cgroup command against the running ``db`` service; skipped without
    one (``just bench-test`` after ``just bench-start`` runs it).
    """
    docker = DockerClient(project=os.environ.get("COMPOSE_PROJECT_NAME") or None)

    if docker.find_service("db") is None:
        pytest.skip("no running db service: start the benchmark stack to run this test")

    recorded = server_settings(docker, POSTGRES_SETTINGS)
    counters = server_counters(docker)

    assert set(POSTGRES_SETTINGS) <= set(recorded["settings"])  # nosec B101 - pytest assertion
    assert set(POSTGRES_SETTINGS) <= set(recorded["key_settings"])  # nosec B101 - pytest assertion
    expected = {"server_start", "num_requested", "num_done", "wal_bytes", "wal_fpi",
                "temp_bytes"}
    assert expected <= set(counters)  # nosec B101 - pytest assertion
    io_keys = [key for key in counters if key.startswith("io_write_bytes:")]
    assert io_keys and not any(" " in key for key in io_keys)  # nosec B101 - pytest assertion
    # cgroup v2 (the benchmark box and CI): every counter the harness reads is there
    cgroup = docker.cgroup_counters("db")
    expected = {"cgroup_write_bytes", "cgroup_oom_kill", CONTAINER_START_KEY}
    assert expected <= set(cgroup)  # nosec B101 - pytest assertion
