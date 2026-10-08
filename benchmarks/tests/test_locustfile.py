"""
Tests for the locustfile's step-health hooks: the recovery record and the exit code.
"""

import json
import os
from types import SimpleNamespace

# importing locust would gevent-patch the whole test process otherwise
os.environ.setdefault("LOCUST_SKIP_MONKEY_PATCH", "1")

import pytest  # noqa: E402
from locust.runners import WorkerRunner  # noqa: E402

from benchmarks import locustfile  # noqa: E402


class FakeRunner:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeWorkerRunner(WorkerRunner):
    """
    A runner of a ``--processes`` worker that connects to nothing and owns no greenlets.
    """

    def __init__(self):
        self.greenlet = None


def step_environment(tmp_path, host=None, runner=None):
    return SimpleNamespace(
        host=host, runner=runner or FakeRunner(), process_exit_code=None,
        parsed_options=SimpleNamespace(csv_prefix=str(tmp_path / "read_u10")))


def recovery(recovered=True, seen=None):
    def api_recovery(base_url, docker, **kwargs):
        if seen is not None:
            seen.append(base_url)
        return {"recovered": recovered, "seconds": 0.0 if recovered else None,
                "rounds": []}
    return api_recovery


def record(tmp_path):
    with open(tmp_path / "read_u10_recovery.json") as fh:
        return json.load(fh)


@pytest.fixture(autouse=True)
def healthy_start_without_docker(monkeypatch):
    monkeypatch.setattr(locustfile, "RECOVERY_S", 60.0)
    monkeypatch.setattr(locustfile, "DockerClient", lambda **kwargs: object())
    monkeypatch.setitem(locustfile._step, "healthy_at_start", True)


def test_a_recovered_step_is_recorded_and_keeps_locusts_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(locustfile, "api_recovery", recovery())
    env = step_environment(tmp_path)

    locustfile._record_recovery(env)

    rec = record(tmp_path)
    assert rec["healthy_at_start"] is True  # nosec B101 - pytest assertion
    assert rec["recovered"] is True  # nosec B101 - pytest assertion
    assert "CUBE_DEBUG" in rec["envelope"]  # nosec B101 - pytest assertion
    assert env.process_exit_code is None  # nosec B101 - pytest assertion
    # the users were stopped before the API was probed
    assert env.runner.stopped  # nosec B101 - pytest assertion


def test_a_step_that_did_not_recover_exits_3(tmp_path, monkeypatch):
    monkeypatch.setattr(locustfile, "api_recovery", recovery(recovered=False))
    env = step_environment(tmp_path)

    locustfile._record_recovery(env)

    assert record(tmp_path)["recovered"] is False  # nosec B101 - pytest assertion
    assert env.process_exit_code == locustfile.UNHEALTHY_EXIT_CODE  # nosec B101 - pytest assertion
    assert locustfile.UNHEALTHY_EXIT_CODE == 3  # nosec B101 - pytest assertion


def test_a_step_that_started_on_an_unhealthy_api_exits_3(tmp_path, monkeypatch):
    monkeypatch.setattr(locustfile, "api_recovery", recovery())
    monkeypatch.setitem(locustfile._step, "healthy_at_start", False)
    env = step_environment(tmp_path)

    locustfile._record_recovery(env)

    assert record(tmp_path)["healthy_at_start"] is False  # nosec B101 - pytest assertion
    assert env.process_exit_code == 3  # nosec B101 - pytest assertion


def test_a_check_that_fails_is_recorded_as_not_recovered(tmp_path, monkeypatch):
    def api_recovery(base_url, docker, **kwargs):
        raise RuntimeError("docker socket gone")

    monkeypatch.setattr(locustfile, "api_recovery", api_recovery)
    env = step_environment(tmp_path)

    locustfile._record_recovery(env)

    rec = record(tmp_path)
    assert rec["recovered"] is False  # nosec B101 - pytest assertion
    assert "docker socket gone" in rec["error"]  # nosec B101 - pytest assertion
    assert env.process_exit_code == 3  # nosec B101 - pytest assertion


def test_both_probes_use_the_host_locust_was_given(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(locustfile, "probe_api",
                        lambda base_url: seen.append(base_url) or [200])
    monkeypatch.setattr(locustfile, "api_recovery", recovery(seen=seen))
    env = step_environment(tmp_path, host="http://other:8000/api/v1/")

    locustfile._probe_before_step(env)
    locustfile._record_recovery(env)

    assert seen == ["http://other:8000/api/v1/"] * 2  # nosec B101 - pytest assertion


def test_no_check_with_a_zero_window(tmp_path, monkeypatch):
    monkeypatch.setattr(locustfile, "RECOVERY_S", 0.0)
    monkeypatch.setattr(locustfile, "api_recovery", recovery(recovered=False))
    env = step_environment(tmp_path)

    locustfile._record_recovery(env)

    assert not (tmp_path / "read_u10_recovery.json").exists()  # nosec B101 - pytest assertion
    assert env.process_exit_code is None  # nosec B101 - pytest assertion


def test_no_check_in_a_worker_process(tmp_path, monkeypatch):
    monkeypatch.setattr(locustfile, "api_recovery", recovery(recovered=False))
    env = step_environment(tmp_path, runner=FakeWorkerRunner())

    locustfile._record_recovery(env)

    assert not (tmp_path / "read_u10_recovery.json").exists()  # nosec B101 - pytest assertion
    assert env.process_exit_code is None  # nosec B101 - pytest assertion
