"""
Tests for benchmarks.executor — per-node params and feed construction.
"""

import threading

from benchmarks.chris_api import ChrisApiError, HttpResult
from benchmarks.executor import _params_for, build_feed, build_feeds
from benchmarks.models import NodeSpec, PluginRole
from benchmarks.topologies import build_fanout_fanin, build_linear

PLUGIN_IDS = {PluginRole.FS: 11, PluginRole.DS: 22, PluginRole.TS: 33}


class FakeCreateApi:
    """
    create_plugin_instance returning sequential ids; fails from call ``fail_at``.
    """

    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.calls = []                   # (plugin_id, params)
        self._n = 0
        self._lock = threading.Lock()

    def create_plugin_instance(self, plugin_id, params):
        with self._lock:
            self._n += 1
            n = self._n

        if self.fail_at is not None and n >= self.fail_at:
            raise ChrisApiError(HttpResult(False, 400, 1.0, None, [], "bad request"))
        
        self.calls.append((plugin_id, dict(params)))
        return {"id": n, "feed_id": 99}


# -- _params_for -----------------------------------------------------------------------

def test_params_for_fs_passthrough():
    node = NodeSpec("root", PluginRole.FS, {"total": "10B", "size": "1B"})
    assert _params_for(node, {}) == {"total": "10B", "size": "1B"}


def test_params_for_ds_sets_previous_id():
    node = NodeSpec("ds0", PluginRole.DS, {"prefix": "ds0_"}, ("root",))
    params = _params_for(node, {"root": 42})
    assert params["previous_id"] == 42
    assert params["prefix"] == "ds0_"


def test_params_for_ts_sets_previous_and_plugininstances():
    node = NodeSpec("merge0", PluginRole.TS, {"filter": ".*"}, ("b0", "b1", "b2"))
    params = _params_for(node, {"b0": 1, "b1": 2, "b2": 3})
    assert params["previous_id"] == 1                 # must be one of the listed ids
    assert params["plugininstances"] == "1,2,3"
    assert params["filter"] == ".*"


# -- build_feed / build_feeds ----------------------------------------------------------

def test_build_feed_links_chain_and_captures_feed():
    api = FakeCreateApi()
    topo = build_linear(depth=2, file_count=1, file_size="1KiB")
    fb = build_feed(api, topo, PLUGIN_IDS)
    
    assert fb.error is None
    assert fb.feed.feed_id == 99 and fb.feed.root_instance_id == 1
    assert fb.feed.instance_ids == (1, 2, 3)

    # ds nodes chain previous_id to the instance created just before them
    assert api.calls[1][1]["previous_id"] == 1
    assert api.calls[2][1]["previous_id"] == 2
    assert [pid for pid, _ in api.calls] == [11, 22, 22]


def test_build_feed_ts_merge_lists_all_branches():
    api = FakeCreateApi()
    topo = build_fanout_fanin(branches=3, file_count=1, file_size="1KiB")
    build_feed(api, topo, PLUGIN_IDS)
    merge_params = api.calls[-1][1]
    assert merge_params["plugininstances"] == "2,3,4"      # the three branch ids
    assert merge_params["previous_id"] == 2
    assert merge_params["groupByInstance"] is True


def test_build_feed_partial_failure_keeps_created_instances():
    api = FakeCreateApi(fail_at=3)        # root and ds0 succeed, ds1 fails
    topo = build_linear(depth=3, file_count=1, file_size="1KiB")
    fb = build_feed(api, topo, PLUGIN_IDS)
    assert fb.error is not None and "bad request" in fb.error
    assert fb.feed is not None            # partial feed kept so it can be cleaned up
    assert fb.feed.instance_ids == (1, 2)
    assert len(fb.instances) == 2


def test_build_feeds_concurrent_returns_one_build_per_feed():
    api = FakeCreateApi()
    topo = build_linear(depth=1, file_count=1, file_size="1KiB")
    builds = build_feeds(api, topo, 4, PLUGIN_IDS)
    assert len(builds) == 4
    assert all(b.error is None for b in builds)
    assert len({b.feed.root_instance_id for b in builds}) == 4
