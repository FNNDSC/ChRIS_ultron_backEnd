"""
Background resource sampler.

Reads every service and plugin-job container at a fixed rate, with one-shot stats reads
(a few milliseconds each) made concurrently, and, when a ``BrokerClient`` is given, the
Celery queue depths on a timer of their own, emitting samples into the ``MetricSink``. A
container's CPU is over the time since its previous reading, so at the default
one-second tick it has the ~1 s window of Docker's own figure. Used as a context manager
so its lifetime is bound to a scenario:

    with StatsSampler(docker, sink, broker=broker) as sampler:
        ...run and poll the scenario...
    summary = sampler.summary()
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import replace
from typing import Callable

from .broker import BrokerClient
from .docker_client import ContainerRef, DockerClient, StatsRead, resource_sample
from .metrics import MetricSink
from .models import QueueSample, SamplerSummary


#: how ``environment.json`` names the sampling method, so bench-compare can tell runs
#: sampled this way from runs sampled another
METHOD = "one-shot reads, CPU between consecutive readings"

#: the share of a tick, from its start, that its reads may take before they count as
#: failed; the rest is left so that the next tick is not late
READ_BUDGET = 0.8


def sampler_record(interval: float, queue_interval: float | None, workers: int) -> dict:
    """
    The sampler's settings as ``environment.json`` records them.
    """
    return {"method": METHOD, "interval_s": interval, "queue_interval_s": queue_interval,
            "workers": workers}


def next_slot(due: float, now: float, interval: float) -> tuple[float, int]:
    """
    When the tick after one due at ``due`` that ended at ``now`` is due, and how many
    ticks that skips: a tick that overran skips the slots it covered rather than running
    them back to back.
    """
    due += interval

    if now <= due:
        return due, 0

    skipped = int((now - due) // interval) + 1
    return due + skipped * interval, skipped


class FixedRate:
    """
    Runs ``tick`` every ``interval`` seconds, start to start, in a thread of its own,
    counting the ticks, the skipped ones, the longest and those that raised.
    """

    def __init__(self, interval: float, tick: Callable[[], None], *, name: str,
                 clock: Callable[[], float] = time.monotonic):
        self.interval = interval
        self.ticks = self.skipped = self.errors = 0
        self.longest = 0.0
        self._tick, self._name, self._clock = tick, name, clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name=self._name, daemon=True)
        self._thread.start()

    def stop(self, *, final_tick: bool = False) -> None:
        """
        Stop, waiting for a running tick to end, then with ``final_tick`` run one more
        in the calling thread.
        """
        self._stop.set()

        if self._thread is not None:
            self._thread.join()
            self._thread = None

        if final_tick:
            self._run_tick()

    def _loop(self) -> None:
        due = self._clock()

        while not self._stop.is_set():
            self._run_tick()
            due, skipped = next_slot(due, self._clock(), self.interval)
            self.skipped += skipped
            self._stop.wait(max(0.0, due - self._clock()))

    def _run_tick(self) -> None:
        started = self._clock()
        try:
            self._tick()
        except Exception:                              # noqa: BLE001 - counted, not fatal
            self.errors += 1
        finally:
            self.ticks += 1
            self.longest = max(self.longest, self._clock() - started)


class StatsSampler:
    def __init__(self, docker: DockerClient, sink: MetricSink, interval: float = 1.0,
                 broker: BrokerClient | None = None, *, queue_interval: float = 0.5,
                 workers: int = 8):
        self._docker = docker
        self._sink = sink
        self._broker = broker if broker is not None and broker.available else None
        self._interval = interval
        self._queue_interval = queue_interval
        self._workers = workers
        self._pool: ThreadPoolExecutor | None = None
        self._since: float | None = None

        self._resources = FixedRate(interval, self._sample_containers, name="stats-sampler")
        self._queues = (FixedRate(queue_interval, self._sample_queues, name="queue-sampler")
                        if self._broker is not None else None)

        self._last: dict[str, dict] = {}               # each container's last frame, by id
        self._started: dict[str, float | None] = {}    # its start time, inspected once
        self._reading: dict[str, Future] = {}          # reads still running past a tick
        self._jobs: set[str] = set()
        self._listed = True
        self._reads = self._failed = self._vanished = self._list_failures = 0
        self._queue_failures = 0

    def start(self) -> StatsSampler:
        self._since = time.time()
        self._pool = ThreadPoolExecutor(self._workers, thread_name_prefix="stats-read")
        self._resources.start()

        if self._queues is not None:
            self._queues.start()
        return self

    def stop(self) -> None:
        """
        Stop both timers, the resources after a closing tick so that the counters'
        window reaches the end of the workload (none when the last tick could not list
        the containers: the engine is not answering); nothing is recorded after this
        returns, and reads still hung on the engine are abandoned.
        """
        if self._queues is not None:
            self._queues.stop()

        self._resources.stop(final_tick=self._listed)

        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None

    def __enter__(self) -> StatsSampler:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def summary(self) -> SamplerSummary:
        queues = self._queues
        return SamplerSummary(
            interval_s=self._interval,
            queue_interval_s=self._queue_interval if queues is not None else None,
            ticks=self._resources.ticks, late_ticks=self._resources.skipped,
            max_tick_s=round(self._resources.longest, 3), reads=self._reads,
            failed_reads=self._failed, vanished=self._vanished,
            list_failures=self._list_failures + self._resources.errors,
            jobs_seen=len(self._jobs),
            queue_ticks=queues.ticks if queues is not None else 0,
            queue_late_ticks=queues.skipped if queues is not None else 0,
            queue_failures=self._queue_failures + (queues.errors if queues else 0))

    # -- ticks -------------------------------------------------------------------------

    def _sample_containers(self) -> None:
        began = time.monotonic()
        self._listed = False
        try:
            if not self._docker.available:             # nothing to read is not a clean tick
                raise RuntimeError(self._docker.unavailable_reason)
            refs = self._docker.sampled_containers()
        except Exception:                              # noqa: BLE001 - counted
            self._list_failures += 1
            return
        self._listed = True

        # the reads run in the pool and the tick waits for them READ_BUDGET of a tick at
        # most, a container whose read is still running being left out until it ends; the
        # samples are made and recorded here, in order
        self._reading = {cid: f for cid, f in self._reading.items() if not f.done()}
        refs = [ref for ref in refs if ref.id not in self._reading]
        reads = {ref.id: self._pool.submit(self._read, ref) for ref in refs}
        budget = self._interval * READ_BUDGET - (time.monotonic() - began)
        done, late = wait(reads.values(), timeout=max(0.0, budget))

        for ref in refs:
            if reads[ref.id] in done:
                started, read = reads[ref.id].result()
                self._started[ref.id] = started
                self._record(replace(ref, started_at=started), read)
            else:
                self._reading[ref.id] = reads[ref.id]

        self._reads += len(late)
        self._failed += len(late)

        listed = {ref.id for ref in refs} | set(self._reading)
        self._last = {cid: frame for cid, frame in self._last.items() if cid in listed}
        self._started = {cid: t for cid, t in self._started.items() if cid in listed}

    def _read(self, ref: ContainerRef) -> tuple[float | None, StatsRead]:
        """
        A container's start time (one inspect, the first time it is seen) and a read.
        """
        if ref.id in self._started:
            started = self._started[ref.id]
        else:
            started = self._docker.started_at(ref.id)
        return started, self._docker.read_stats(ref.id)

    def _record(self, ref: ContainerRef, read: StatsRead) -> None:
        self._reads += 1

        if read.vanished:
            self._vanished += 1
            self._last.pop(ref.id, None)
            return

        if read.frame is None:
            self._failed += 1
            return

        # a restart, which keeps the id, shows as counters that went backwards
        self._sink.record_resource(
            resource_sample(ref, read.frame, self._last.get(ref.id), since=self._since))
        self._last[ref.id] = read.frame

        if ref.kind == "job":
            self._jobs.add(ref.id)

    def _sample_queues(self) -> None:
        depths = self._broker.depths()

        if not depths:
            self._queue_failures += 1
            return

        now = time.time()
        for queue, depth in depths.items():
            self._sink.record_queue(QueueSample(now, queue, depth))
