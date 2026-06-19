"""
Environment / hardware manifest collection.

Auto-collects what it can (Docker engine info gives the *host* CPU/mem, image ids,
versions) and reads the envelope knobs + git provenance from environment variables the
``justfile`` injects. Manual hardware fields are left as explicit placeholders for the
generated report.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from .chris_api import ChrisApi
from .docker_client import DockerClient
from .metrics import percentile


#: envelope knobs recorded verbatim from the environment (set by the bench compose/just)
ENVELOPE_KEYS = (
    "CUBE_CELERY_POLL_INTERVAL", "CUBE_UVICORN_WORKERS", "CUBE_DB_POOL_MIN_SIZE",
    "CUBE_DB_POOL_MAX_SIZE", "CUBE_DB_POOL_TIMEOUT", "CUBE_DB_MAX_CONNECTIONS",
    "CUBE_WORKER_MAINS_CONCURRENCY", "PFCON_WORKERS", "STORAGE_ENV",
)


def collect_environment(docker: DockerClient, *, env: "os._Environ | dict | None" = None,
                        image_services: tuple[str, ...] = ("chris", "pfcon")) -> dict:
    env = os.environ if env is None else env
    info = docker.info()
    version = docker.version()

    images = {}

    for service in image_services:
        container = docker.find_service(service)

        if container is not None:
            images[service] = {"image_id": container.image.id,
                               "tags": container.image.tags}
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "operating_system": info.get("OperatingSystem"),
            "kernel_version": info.get("KernelVersion"),
            "architecture": info.get("Architecture"),
            "ncpu": info.get("NCPU"),
            "mem_total_bytes": info.get("MemTotal"),
            "docker_root_dir": info.get("DockerRootDir"),
            "server_version": info.get("ServerVersion"),
        },
        "docker": {
            "engine_version": version.get("Version"),
            "api_version": version.get("ApiVersion"),
            "platform": (version.get("Platform") or {}).get("Name"),
        },
        "images": images,
        "git": {"commit": env.get("GIT_COMMIT"), "dirty": env.get("GIT_DIRTY")},
        "storage_mode": env.get("STORAGE_ENV", "fslink"),
        "envelope": {k: env.get(k) for k in ENVELOPE_KEYS},
        "noise_floor": None,                       # filled by measure_noise_floor()
        "manual_fields": {
            "storage_device_type_throughput": "TODO",
            "power_thermal_mode": "TODO",
            "other_significant_workloads": "TODO",
        },
    }


def measure_noise_floor(api: ChrisApi, samples: int = 20) -> dict:
    """
    Idle API latency, to quantify the measurement noise floor.
    """
    latencies: list[float] = []

    for _ in range(samples):
        t0 = time.perf_counter()

        try:
            api.health()
        except Exception:  # noqa: BLE001
            pass

        latencies.append((time.perf_counter() - t0) * 1000.0)

    return {
        "health_p50_ms": round(percentile(latencies, 50), 1),
        "health_p95_ms": round(percentile(latencies, 95), 1),
        "samples": samples,
    }
