"""
Locust control-plane load test for CUBE — the deferred Layer-1 (control plane / RED)
from STRATEGY §4, built on the ``chris_api`` Collection+JSON seam.

The data-plane harness (``run_bench``) measures orchestration (makespan, DAG execution).
This complements it by driving *concurrent API clients* against the control-plane
endpoints (list feeds/instances/files, plugin search, create instance) and reporting RED
metrics — Rate, Errors, Duration percentiles — via Locust's own statistics. It is the
right tool to find the API saturation knee, error onset, and DB connection-pool
exhaustion under client concurrency, which the data plane does not exercise.

Run headless via ``just bench-locust``, e.g.::

    just bench-locust '-u 100 -r 20 -t 3m'      # 100 users, ramp 20/s, 3 minutes

``host`` is taken from ``CUBE_URL`` (set on the benchmark service), so no ``--host`` is
needed. Pure Collection+JSON helpers are reused from ``chris_api`` (the shared seam).
"""

from __future__ import annotations

import json
import os

from locust import HttpUser, between, task

from benchmarks.chris_api import CJ, _items, _template


USERNAME = os.environ.get("CUBE_USERNAME", "chris")
PASSWORD = os.environ.get("CUBE_PASSWORD", "chris1234")

FS_PLUGIN = os.environ.get("BENCH_LOCUST_FS_PLUGIN", "dbg-bigfiles")

#: small fs payload (~10 files of 1 KiB) — keeps the write path cheap; jobs still spawn
FS_PARAMS = {"total": "10240B", "size": "1024B"}

#: the create task spawns real DAGs, so it is opt-in (BENCH_LOCUST_WRITE=1). Default is a
#: clean read-only control-plane saturation sweep that doesn't flood the compute side.
WRITE_ENABLED = os.environ.get("BENCH_LOCUST_WRITE", "").lower() in ("1", "true", "yes")


class CubeUser(HttpUser):
    """
    One simulated API client: authenticates once via a DRF token, then exercises the
    control-plane endpoints. Reads dominate (the cleanest saturation signal); a low-weight
    create exercises the write path too.
    """

    host = os.environ.get("CUBE_URL", "http://chris:8000/api/v1/")
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        with self.client.post("auth-token/",
                              json={"username": USERNAME, "password": PASSWORD},
                              name="auth-token", catch_response=True) as r:
            if r.status_code // 100 != 2:
                r.failure(f"auth HTTP {r.status_code}")
                self.fs_id = None
                return
            
            token = r.json().get("token")
            if not token:
                r.failure("no token in auth response")
                self.fs_id = None
                return
            r.success()

        self.client.headers.update({"Authorization": f"Token {token}", "Accept": CJ})
        self.fs_id = self._resolve_fs_id()

    def _resolve_fs_id(self):
        with self.client.get("plugins/search/", params={"name_exact": FS_PLUGIN},
                             name="search-plugins", catch_response=True) as r:
            self._check(r)

            try:
                items = _items(r.json())
                return int(items[0]["id"]) if items else None
            except Exception:                      # noqa: BLE001 - best effort
                return None

    # -- read tasks (control-plane RED) ----------------------------------------------

    @task(6)
    def list_feeds(self) -> None:
        self._get("", {"limit": 10}, "list-feeds")

    @task(6)
    def list_instances(self) -> None:
        self._get("plugins/instances/", {"limit": 10}, "list-instances")

    @task(4)
    def list_files(self) -> None:
        self._get("userfiles/", {"limit": 10}, "list-files")

    @task(2)
    def search_plugins(self) -> None:
        self._get("plugins/search/", {"name_exact": FS_PLUGIN}, "search-plugins")

    # -- write task (exercises the create path; spawns a small job) -------------------

    @task(1)
    def create_instance(self) -> None:
        if not WRITE_ENABLED or not getattr(self, "fs_id", None):
            return
        
        body = json.dumps(_template(FS_PARAMS))

        with self.client.post(f"plugins/{self.fs_id}/instances/", data=body,
                              headers={"Content-Type": CJ}, name="create-instance",
                              catch_response=True) as r:
            self._check(r)

    # -- helpers ----------------------------------------------------------------------

    def _get(self, path: str, params: dict, name: str) -> None:
        with self.client.get(path, params=params, name=name, catch_response=True) as r:
            self._check(r)

    @staticmethod
    def _check(r) -> None:
        if r.status_code // 100 == 2:
            r.success()
        else:
            r.failure(f"HTTP {r.status_code}")
