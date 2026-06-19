"""
Recovery and settling between scenarios.

After a hard failure the harness captures service logs, reaps leftover plugin-job
containers (reusing the ``justfile`` reap pattern), waits for CUBE health to return, and
optionally restarts services — then the sweep continues with the next axis.

``wait_for_quiescence`` is the between-scenario settling gate: feed deletion in CUBE is
asynchronous (Celery), so a scenario's cleanup keeps churning the DB after the DELETEs
are accepted; starting the next level immediately would contaminate its latency, CPU and
DB-delta measurements.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .chris_api import ChrisApi
from .docker_client import DockerClient


def wait_for_health(api: ChrisApi, timeout: float, interval: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if api.health():
                return True
        except Exception:                              # noqa: BLE001 - keep polling
            pass
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
