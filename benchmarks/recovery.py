"""
Recovery and settling between scenarios.

After a hard failure the harness captures service logs, reaps leftover plugin-job
containers (reusing the ``justfile`` reap pattern), waits for CUBE health to return, and
optionally restarts services — then the sweep continues with the next axis.

``wait_for_quiescence`` is the between-scenario settling gate: feed deletion in CUBE is
asynchronous (Celery), so a scenario's cleanup keeps churning the DB after the DELETEs
are accepted; starting the next level immediately would contaminate its latency, CPU and
DB-delta measurements.

``api_recovery`` is the control-plane counterpart, run after every Locust step: whether
the API answers normally again once the load stops, so a stack that an overload left
broken cannot pass as the next step's measurement.
"""

from __future__ import annotations

import contextlib
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

import requests

from .chris_api import CJ, ChrisApi
from .docker_client import DockerClient
from .pg_stats import connection_states


#: a database-backed endpoint that needs no login
PROBE_PATH = "plugins/?limit=1"

#: what ``core.utils.start_db_pool_stats_logger`` logs for each API worker
POOL_STATS_RE = re.compile(r"db_pool_stats (\{.*\})")


def wait_for_health(api: ChrisApi, timeout: float, interval: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):           # keep polling through transient errors
            if api.health():
                return True

        time.sleep(interval)
    return False


def wait_for_quiescence(get_counts: Callable[[], dict], before: dict, timeout_s: float,
                        interval_s: float = 2.0) -> bool:
    """
    Wait until global feed/instance counts settle back to (or below) the
    pre-scenario baseline; returns False on timeout. Counts are checked at least once.
    """
    deadline = time.monotonic() + timeout_s

    while True:
        counts = get_counts()

        if (counts["feeds"] <= before["feeds"]
                and counts["instances"] <= before["instances"]):
            return True
        
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval_s)


def capture_logs(docker: DockerClient, out_dir: Path, tail: int = 200) -> list[str]:
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []

    for container in docker.service_containers():
        service = container.labels.get("com.docker.compose.service", container.name)
        (logs_dir / f"{service}.log").write_text(docker.logs(container, tail=tail))
        captured.append(service)

    return captured


def recover_after_failure(docker: DockerClient, api: ChrisApi, out_dir: Path, *,
                          services: tuple[str, ...] = (), restart: bool = False,
                          health_timeout: float = 30.0, log_tail: int = 200) -> dict:
    summary: dict = {
        "logs_captured": capture_logs(docker, out_dir, tail=log_tail),
        "jobs_reaped": docker.reap_jobs(),
    }

    summary["healthy"] = wait_for_health(api, health_timeout)

    if not summary["healthy"] and restart and services:
        summary["restarted"] = [s for s in services if docker.restart_service(s)]
        summary["healthy_after_restart"] = wait_for_health(api, health_timeout)
    return summary


# -- API recovery after a load step ------------------------------------------------------

def http_burst(url: str, n: int, timeout: float) -> list:
    """
    Send ``n`` concurrent GETs, each on a fresh connection so that they are likely to
    spread over the API's worker processes (the kernel does not guarantee it), and return
    their status codes (None for no response).
    """
    def get(_):
        try:
            return requests.get(url, headers={"Accept": CJ}, timeout=timeout).status_code
        except requests.RequestException:
            return None

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(get, range(n)))


def all_ok(statuses: list) -> bool:
    return bool(statuses) and all(s is not None and 200 <= s < 300 for s in statuses)


def probe_api(base_url: str, n: int = 16, timeout: float = 15.0) -> list:
    """
    One burst of ``PROBE_PATH`` requests; ``timeout`` must outlast the DB pool's wait so
    that a worker without connections answers 500 instead of looking merely slow.
    """
    return http_burst(base_url.rstrip("/") + "/" + PROBE_PATH, n, timeout)


def parse_pool_stats(log_text: str) -> dict:
    """
    The latest ``db_pool_stats`` record of each API worker (keyed by pid) in a log.
    """
    latest: dict = {}

    for match in POOL_STATS_RE.finditer(log_text):
        with contextlib.suppress(ValueError, KeyError, TypeError):
            record = json.loads(match.group(1))
            latest[record["pid"]] = record
    return latest


def probe_recovery(probe: Callable[[], list], *, window_s: float, interval_s: float = 5.0,
                   pools: Optional[Callable[[float], dict]] = None, settle_s: float = 0.0,
                   workers: Optional[int] = None,
                   clock: Optional[Callable[[], float]] = None,
                   sleep: Optional[Callable[[float], None]] = None) -> dict:
    """
    Probe the API every ``interval_s`` until a round passes or ``window_s`` has elapsed
    (one round at least), and return whether it ``recovered``, the ``seconds`` it took
    and every round.

    A round passes when every request of a ``probe()`` burst succeeded: with several
    workers, one answer can come from the only healthy one, and a burst only makes it likely
    that every worker answers some of it. With ``pools(since)``, the
    latest pool counters each worker logged after ``since``, a passing burst then waits
    ``settle_s`` for every worker (``workers`` of them, if given) to log its pool once
    more, and also needs each of them to have nothing checked out. Every round records
    the counters it saw, a failed one those logged during its burst.
    """
    clock = clock or time.time
    sleep = sleep or time.sleep
    start = clock()
    rounds = []

    while True:
        t0 = clock()
        statuses = probe()
        ok = all_ok(statuses)
        record = {"t": round(t0 - start, 1),
                  "statuses": dict(Counter(str(s) for s in statuses))}

        if pools is not None:
            since = t0      # a failed burst lasts long enough for the workers to log

            if ok:
                since = clock()
                sleep(settle_s)
            latest = pools(since)
            record["checked_out"] = {str(pid): s.get("checked_out")
                                     for pid, s in latest.items()}
            ok = (ok and bool(latest)
                  and all(n == 0 for n in record["checked_out"].values())
                  and (workers is None or len(latest) >= workers))

        record["ok"] = ok
        rounds.append(record)

        if ok:
            return {"recovered": True, "seconds": record["t"], "rounds": rounds}

        if clock() - start >= window_s:
            return {"recovered": False, "seconds": None, "rounds": rounds}
        sleep(interval_s)


def api_recovery(base_url: str, docker: DockerClient, *, window_s: float,
                 stats_interval_s: float = 0.0, workers: Optional[int] = None,
                 interval_s: float = 5.0, service: str = "chris") -> dict:
    """
    ``probe_recovery`` against the API at ``base_url``, also checking the pool counters
    its workers log when ``stats_interval_s`` says they do, plus the database's
    connection states at the end.
    """
    container = docker.find_service(service) if stats_interval_s > 0 else None

    def pools(since):
        return parse_pool_stats(docker.logs(container, tail="all", since=since))

    result = probe_recovery(lambda: probe_api(base_url), window_s=window_s,
                            interval_s=interval_s,
                            pools=pools if container is not None else None,
                            settle_s=stats_interval_s + 1.0, workers=workers)
    result["pools_checked"] = container is not None
    result["connections"] = connection_states(docker)
    return result
