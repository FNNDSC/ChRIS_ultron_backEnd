"""Low-level wrapper over the Docker SDK (against the mounted socket).

One small adapter reused by the stats sampler, the recovery routine, and environment
collection — the same access pattern the ``justfile`` ``reap-plugin-instances`` recipe
uses (``docker.from_env()`` + label filters). Engine-agnostic: a podman socket exposing
the Docker API works too.
"""

from __future__ import annotations

import contextlib
from typing import Optional

from .models import ResourceSample


#: pfcon labels every plugin-job container with this (see docker-compose.yml JOB_LABELS)
JOB_LABEL = "org.chrisproject.miniChRIS=plugininstance"


class DockerClient:
    """
    Docker access for sampling/recovery/environment. Degrades to a no-op if the
    socket is unavailable (e.g. a non-root container on Docker Desktop) so the rest of
    the harness still runs — resource sampling and recovery are best-effort by design.
    """

    def __init__(self, project: Optional[str] = None, *, job_label: str = JOB_LABEL,
                 exclude_services: tuple[str, ...] = ()):
        self.project = project
        self.job_label = job_label
        self.exclude_services = exclude_services
        self._docker = None
        self.unavailable_reason: Optional[str] = None

        try:
            import docker  # imported lazily so pure modules never need the SDK
            client = docker.from_env()
            client.ping()
            self._docker = client
        except Exception as exc:  # noqa: BLE001 - optional dependency
            self.unavailable_reason = str(exc)

    @property
    def available(self) -> bool:
        return self._docker is not None

    # -- container discovery ---------------------------------------------------------

    def service_containers(self) -> list:
        if not self._docker:
            return []
        
        if self.project:
            flt = {"label": f"com.docker.compose.project={self.project}"}
        else:
            flt = {"label": "com.docker.compose.service"}
        
        return [c for c in self._docker.containers.list(filters=flt)
                if c.labels.get("com.docker.compose.service") not in self.exclude_services]

    def job_containers(self, all_states: bool = False) -> list:
        if not self._docker:
            return []
        return self._docker.containers.list(all=all_states,
                                            filters={"label": self.job_label})

    def find_service(self, service: str) -> Optional[object]:
        for c in self.service_containers():
            if c.labels.get("com.docker.compose.service") == service:
                return c
        return None

    # -- sampling --------------------------------------------------------------------

    def sample(self, container) -> ResourceSample:
        import time

        stats = container.stats(stream=False)
        kind = "job" if self.job_label.split("=")[0] in container.labels else "service"
        mem = stats.get("memory_stats", {})
        blkio = _blkio(stats)

        return ResourceSample(
            t=time.time(),
            container=container.labels.get("com.docker.compose.service", container.name),
            kind=kind,
            cpu_pct=_cpu_pct(stats),
            mem_bytes=float(mem.get("usage", 0) or 0),
            mem_limit_bytes=float(mem.get("limit", 0) or 0),
            blkio_read_bytes=blkio[0],
            blkio_write_bytes=blkio[1],
            pids=int(stats.get("pids_stats", {}).get("current", 0) or 0),
        )

    # -- ops -------------------------------------------------------------------------

    def logs(self, container, tail: int = 200) -> str:
        try:
            return container.logs(tail=tail).decode("utf-8", "replace")
        except Exception as exc:                       # noqa: BLE001 - best effort
            return f"<could not read logs: {exc}>"

    def reap_jobs(self) -> int:
        removed = 0
        for c in self.job_containers(all_states=True):
            with contextlib.suppress(Exception):       # best effort
                c.remove(force=True)
                removed += 1
        return removed

    def exec_in_service(self, service: str, cmd: list) -> "tuple[int, str]":
        """
        Run a command inside a service container; (-1, reason) when unavailable.
        """
        container = self.find_service(service)

        if container is None:
            return -1, f"service {service!r} not running"
        
        try:
            code, output = container.exec_run(cmd)
            return code, output.decode("utf-8", "replace")
        except Exception as exc:                       # noqa: BLE001 - best effort
            return -1, str(exc)

    def service_env(self, service: str) -> dict:
        """
        Environment variables of a service container (e.g. POSTGRES_USER).
        """
        container = self.find_service(service)
        if container is None:
            return {}
        env = container.attrs.get("Config", {}).get("Env", []) or []
        return dict(item.split("=", 1) for item in env if "=" in item)

    def restart_service(self, service: str) -> bool:
        c = self.find_service(service)
        if c is None:
            return False
        try:
            c.restart()
            return True
        except Exception:                              # noqa: BLE001
            return False

    def info(self) -> dict:
        try:
            return self._docker.info()
        except Exception:                              # noqa: BLE001
            return {}

    def version(self) -> dict:
        try:
            return self._docker.version()
        except Exception:                              # noqa: BLE001
            return {}


def _cpu_pct(stats: dict) -> float:
    cpu = stats.get("cpu_stats", {})
    pre = stats.get("precpu_stats", {})

    cpu_delta = (cpu.get("cpu_usage", {}).get("total_usage", 0)
                 - pre.get("cpu_usage", {}).get("total_usage", 0))
    
    system_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
    
    ncpu = (cpu.get("online_cpus")
            or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1)
    
    if system_delta > 0 and cpu_delta > 0:
        return round((cpu_delta / system_delta) * ncpu * 100.0, 2)
    return 0.0


def _blkio(stats: dict) -> tuple[float, float]:
    read = write = 0.0
    
    for entry in stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []:
        op = entry.get("op", "").lower()
        
        if op == "read":
            read += entry.get("value", 0)
        elif op == "write":
            write += entry.get("value", 0)
    return read, write
