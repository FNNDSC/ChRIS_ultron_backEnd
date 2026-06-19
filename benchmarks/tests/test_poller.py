from benchmarks.models import InstanceRef, PluginRole
from benchmarks.poller import ProgressProbe, poll_to_completion


class FakeApi:
    """
    Returns successive scripted status scans; repeats the last one when exhausted.
    """

    def __init__(self, scans):
        self.scans = list(scans)
        self.i = 0

    def get_feed_instances(self, feed_id, **kwargs):
        scan = self.scans[min(self.i, len(self.scans) - 1)]
        self.i += 1
        return scan


class FakeDocker:
    def __init__(self, available=True, jobs=()):
        self.available = available
        self._jobs = list(jobs)

    def job_containers(self, all_states=False):
        return self._jobs


POLL = dict(poll_every=0.001, scenario_timeout=5, no_progress_timeout=5)


def test_early_return_when_no_feeds():
    res = poll_to_completion(FakeApi([]), [], [], **POLL)
    assert res.terminal and not res.no_progress and not res.timed_out
    assert res.timelines == []


def test_reaches_terminal_and_counts_finals():
    instances = [InstanceRef(1, 9, "root", PluginRole.FS),
                 InstanceRef(2, 9, "ds0", PluginRole.DS)]
    scans = [
        [{"id": 1, "status": "started"}, {"id": 2, "status": "created"}],
        [{"id": 1, "status": "finishedSuccessfully"},
         {"id": 2, "status": "finishedSuccessfully"}],
    ]
    res = poll_to_completion(FakeApi(scans), [9], instances, **POLL)
    assert res.terminal and not res.timed_out and not res.no_progress
    assert res.final_status_counts.get("finishedSuccessfully") == 2
    assert res.hard_failures == ()


def test_detects_hard_failure():
    instances = [InstanceRef(1, 9, "root", PluginRole.FS)]
    res = poll_to_completion(FakeApi([[{"id": 1, "status": "finishedWithError"}]]),
                             [9], instances, **POLL)
    assert res.terminal
    assert any("finishedWithError" in h for h in res.hard_failures)


def test_no_progress_fires_when_status_never_changes():
    instances = [InstanceRef(1, 9, "root", PluginRole.FS)]
    res = poll_to_completion(FakeApi([[{"id": 1, "status": "waiting"}]]),
                             [9], instances, poll_every=0.001,
                             scenario_timeout=5, no_progress_timeout=0.02)
    assert res.no_progress and not res.terminal and not res.timed_out


def test_scenario_timeout_fires_before_no_progress():
    instances = [InstanceRef(1, 9, "root", PluginRole.FS)]
    res = poll_to_completion(FakeApi([[{"id": 1, "status": "waiting"}]]),
                             [9], instances, poll_every=0.001,
                             scenario_timeout=0.02, no_progress_timeout=5)
    assert res.timed_out and not res.no_progress and not res.terminal


def test_progress_probe_keeps_no_progress_at_bay():
    # status never transitions, but the probe vouches for in-phase work; the scenario
    # timeout (not the no-progress window) must end the poll
    instances = [InstanceRef(1, 9, "root", PluginRole.FS)]
    res = poll_to_completion(FakeApi([[{"id": 1, "status": "registeringFiles"}]]),
                             [9], instances, poll_every=0.001,
                             scenario_timeout=0.05, no_progress_timeout=0.01,
                             progress_probe=lambda statuses: True)
    assert res.timed_out and not res.no_progress


# -- ProgressProbe -----------------------------------------------------------------------

def test_probe_work_statuses_count_as_progress():
    probe = ProgressProbe(docker=FakeDocker(jobs=[]))
    assert probe({1: "registeringFiles"})
    assert probe({1: "uploading"})
    assert probe({1: "copying"})


def test_probe_started_requires_running_job_container():
    assert ProgressProbe(FakeDocker(jobs=["c1"]))({1: "started"})
    assert not ProgressProbe(FakeDocker(jobs=[]))({1: "started"})


def test_probe_started_is_lenient_without_docker():
    assert ProgressProbe(docker=None)({1: "started"})
    assert ProgressProbe(FakeDocker(available=False))({1: "started"})


def test_probe_queue_states_are_not_progress():
    probe = ProgressProbe(FakeDocker(jobs=["c1"]))
    assert not probe({1: "created", 2: "waiting", 3: "scheduled"})
    assert not probe({})
