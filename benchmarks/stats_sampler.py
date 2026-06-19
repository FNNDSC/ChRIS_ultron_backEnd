"""
Background resource sampler.

Periodically snapshots service and plugin-job containers via ``DockerClient`` — and,
when a ``BrokerClient`` is given, the Celery queue depths — emitting samples into the
``MetricSink``. Used as a context manager so its lifetime is bound to a scenario:

    with StatsSampler(docker, sink, broker=broker, interval=2.0):
        ...run and poll the scenario...
"""

from __future__ import annotations

import threading
import time

from .broker import BrokerClient
from .docker_client import DockerClient
from .metrics import MetricSink
from .models import QueueSample


class StatsSampler:
    def __init__(self, docker: DockerClient, sink: MetricSink, interval: float = 2.0,
                 broker: "BrokerClient | None" = None):
        self._docker = docker
        self._sink = sink
        self._broker = broker
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "StatsSampler":
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="stats-sampler",
                                        daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None

    def __enter__(self) -> "StatsSampler":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self._interval)

    def _sample_once(self) -> None:
        if self._broker is not None:
            now = time.time()
            for queue, depth in self._broker.depths().items():
                self._sink.record_queue(QueueSample(now, queue, depth))
        
        try:
            containers = self._docker.service_containers() + self._docker.job_containers()
        except Exception:                              # noqa: BLE001 - best effort
            return
        
        for container in containers:
            try:
                self._sink.record_resource(self._docker.sample(container))
            except Exception:                          # noqa: BLE001 - skip flaky reads
                continue
