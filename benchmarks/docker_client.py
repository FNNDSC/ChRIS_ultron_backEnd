"""Low-level wrapper over the Docker SDK (against the mounted socket).

One small adapter reused by the stats sampler, the recovery routine, and environment
collection — the same access pattern the ``justfile`` ``reap-plugin-instances`` recipe
uses (``docker.from_env()`` + label filters). Engine-agnostic: a podman socket exposing
the Docker API works too.
"""

from __future__ import annotations

import contextlib
import time

import docker
from docker.errors import ImageNotFound

from .models import ResourceSample


#: pfcon labels every plugin-job container with this (see docker-compose.yml JOB_LABELS)
JOB_LABEL = "org.chrisproject.miniChRIS=plugininstance"

#: run inside a container, it reads the container's own cgroup v2 files (each container
#: gets a private cgroup namespace): ``io.stat`` is what ``docker stats`` reports as block
#: I/O, and the swap and OOM-kill counters are ones the stats API leaves out
CGROUP_COUNTERS_CMD = [
    "sh", "-c",
    "cat /sys/fs/cgroup/io.stat; "
    "grep -E '^(pswpin|pswpout) ' /sys/fs/cgroup/memory.stat; "
    "grep '^oom_kill ' /sys/fs/cgroup/memory.events",
]

_CGROUP_KEYS = ("pswpin", "pswpout", "oom_kill")

#: the cgroup counters' identity: when it differs between two readings the container
#: restarted in between and its counters started again from zero
CONTAINER_START_KEY = "cgroup_container_started_at"


class DockerClient:
    """
    Docker access for sampling/recovery/environment. Degrades to a no-op if the
    socket is unavailable (e.g. a non-root container on Docker Desktop) so the rest of
    the harness still runs — resource sampling and recovery are best-effort by design.
    """

    def __init__(self, project: str | None = None, *, job_label: str = JOB_LABEL,
                 exclude_services: tuple[str, ...] = ()):
        self.project = project
        self.job_label = job_label
        self.exclude_services = exclude_services
        self._docker = None
        self.unavailable_reason: str | None = None

        try:
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

    def find_service(self, service: str) -> object | None:
        for c in self.service_containers():
            if c.labels.get("com.docker.compose.service") == service:
                return c
        return None

    # -- sampling --------------------------------------------------------------------

    def sample(self, container) -> ResourceSample:
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

    def logs(self, container, tail: int | str = 200, since: float | None = None) -> str:
        """
        The container's last ``tail`` log lines (``"all"`` for every one), only those
        written after the epoch time ``since`` when given.
        """
        try:
            return container.logs(tail=tail, since=since).decode("utf-8", "replace")
        except Exception as exc:                       # noqa: BLE001 - best effort
            return f"<could not read logs: {exc}>"

    def reap_jobs(self) -> int:
        removed = 0
        for c in self.job_containers(all_states=True):
            with contextlib.suppress(Exception):       # best effort
                c.remove(force=True)
                removed += 1
        return removed

    def exec_in_service(self, service: str, cmd: list) -> tuple[int, str]:
        """
        Run a command inside a service container; (-1, reason) when unavailable.
        """
        container = self.find_service(service)

        if container is None:
            return -1, f"service {service!r} not running"
        return _exec(container, cmd)

    def cgroup_counters(self, service: str) -> dict:
        """
        Counters of a service container's cgroup since it started:
        ``cgroup_write_bytes`` (bytes written to disk), ``cgroup_pswpout`` and
        ``cgroup_pswpin`` (pages swapped out and in) and ``cgroup_oom_kill``, with the
        container's start time under ``CONTAINER_START_KEY``. Only the counters that
        could be read are present, so ``{}`` when none could.
        """
        container = self.find_service(service)

        if container is None:
            return {}

        code, out = _exec(container, CGROUP_COUNTERS_CMD)
        counters = {} if code == -1 else parse_cgroup_counters(out)

        if counters:
            counters[CONTAINER_START_KEY] = (container.attrs.get("State") or {}).get(
                "StartedAt")
        return counters

    def service_limits(self) -> dict:
        """
        The resource limits the engine applies to each running service container:
        ``cpus``, ``mem_limit`` and ``memswap_limit`` (bytes; -1 = unlimited swap) and
        ``shm_size`` (bytes), each ``None`` when unset.
        """
        limits = {}

        for container in self.service_containers():
            host = container.attrs.get("HostConfig", {}) or {}
            service = container.labels.get("com.docker.compose.service", container.name)

            limits[service] = {"cpus": _cpus(host),
                               "mem_limit": host.get("Memory") or None,
                               "memswap_limit": host.get("MemorySwap") or None,
                               "shm_size": host.get("ShmSize") or None}
        return limits

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

    def image_info(self, ref: str | None) -> dict | None:
        """
        The local image an image reference resolves to (``image_record``); ``None`` when
        it is not present or Docker is unavailable, ``{"error": ...}`` when Docker
        could not tell.
        """
        if not self._docker or not ref:
            return None

        try:
            return image_record(self._docker.images.get(ref))
        except ImageNotFound:
            return None
        except Exception as exc:                       # noqa: BLE001 - reported, not raised
            return {"error": str(exc)}


def image_record(image) -> dict:
    """
    What identifies a local image: its id, the digests it is known by (sorted) and its
    architecture. The id of one image differs between image stores (overlay2,
    containerd); the digest of a pulled image does not. On overlay2 only a pulled image
    has digests; on containerd a local build has one of its own.
    """
    attrs = getattr(image, "attrs", None) or {}
    return {"image_id": image.id, "repo_digests": sorted(attrs.get("RepoDigests") or []),
            "architecture": attrs.get("Architecture")}


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


def _exec(container, cmd: list) -> tuple[int, str]:
    try:
        code, output = container.exec_run(cmd)
        return code, output.decode("utf-8", "replace")
    except Exception as exc:                           # noqa: BLE001 - best effort
        return -1, str(exc)


def _cpus(host: dict) -> float | None:
    """
    A container's CPU limit: Docker sets ``NanoCpus``, while Podman can report the
    same limit as a CFS quota over its period.
    """
    if host.get("NanoCpus"):
        return host["NanoCpus"] / 1e9

    quota, period = host.get("CpuQuota") or 0, host.get("CpuPeriod") or 0
    return quota / period if quota > 0 and period > 0 else None


def parse_cgroup_counters(text: str) -> dict:
    """
    Parse ``CGROUP_COUNTERS_CMD`` output: ``io.stat`` lines (``<major:minor> wbytes=N
    ...``, summed over devices) and ``<key> <value>`` lines from ``memory.stat`` and
    ``memory.events``; anything else is ignored.
    """
    counters: dict[str, int] = {}
    written = None

    for line in text.splitlines():
        fields = line.split()

        if fields and ":" in fields[0]:                # io.stat: one line per device
            for item in fields[1:]:
                key, _, value = item.partition("=")

                if key == "wbytes" and value.isdigit():
                    written = (written or 0) + int(value)

        elif len(fields) == 2 and fields[0] in _CGROUP_KEYS and fields[1].isdigit():
            counters[f"cgroup_{fields[0]}"] = int(fields[1])

    if written is not None:
        counters["cgroup_write_bytes"] = written
    return counters


def _blkio(stats: dict) -> tuple[float, float]:
    read = write = 0.0
    
    for entry in stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []:
        op = entry.get("op", "").lower()
        
        if op == "read":
            read += entry.get("value", 0)
        elif op == "write":
            write += entry.get("value", 0)
    return read, write
