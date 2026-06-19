"""
Shared data contracts for the benchmark harness.

These frozen/lightweight dataclasses are the *only* coupling between layers: pure
logic modules produce and consume them, adapters emit them, and the runner wires
the flow. Keeping the contracts here (and nowhere else) keeps every other module
small and independently testable.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- plugin instance status vocabulary (mirrors chris_backend/plugininstances/enums.py) ---

ACTIVE_STATUSES: frozenset[str] = frozenset(
    {"created", "waiting", "copying", "scheduled", "started", "uploading", 
    "registeringFiles"}
)

INACTIVE_STATUSES: frozenset[str] = frozenset(
    {"finishedSuccessfully", "finishedWithError", "cancelled"}
)

HARD_FAILURE_STATUSES: frozenset[str] = frozenset({"finishedWithError", "cancelled"})

#: phases whose *duration* we report (active phases, in order)
PHASE_ORDER: tuple[str, ...] = (
    "created",
    "waiting",
    "copying",
    "scheduled",
    "started",
    "uploading",
    "registeringFiles",
)


class PluginRole(str, enum.Enum):
    """
    The three plugin kinds the harness drives.
    """
    FS = "fs"   # dbg-bigfiles  — feed root, generates data
    DS = "ds"   # pl-simpledsapp — downstream node
    TS = "ts"   # pl-topologicalcopy — fan-in / merge


class Verdict(str, enum.Enum):
    PASS = "PASS"
    DEGRADED = "DEGRADED"
    FAIL = "FAIL"


# --- topology shape (pure; no API ids) ------------------------------------------------

@dataclass(frozen=True)
class NodeSpec:
    """
    One logical node of a topology, before it is instantiated in CUBE.

    ``params`` carries only plugin-specific parameters (e.g. dbg-bigfiles total/size,
    simpledsapp sleepLength). Linkage params (``previous_id`` / ``plugininstances``)
    are derived by the executor from ``parents`` once real instance ids are known.
    """
    key: str
    role: PluginRole
    params: dict
    parents: tuple[str, ...] = ()   # logical keys; () for the FS root


@dataclass(frozen=True)
class Topology:
    kind: str                       # "linear" | "fanout_fanin" | "diamond"
    nodes: tuple[NodeSpec, ...]     # topological order: parents precede children
    params: dict                    # shape params that generated it (for recording)


# --- instantiated references ----------------------------------------------------------

@dataclass(frozen=True)
class FeedRef:
    feed_id: int
    root_instance_id: int
    instance_ids: tuple[int, ...]


@dataclass(frozen=True)
class InstanceRef:
    """
    A created instance plus the logical node it came from (used to seed timelines).
    """
    instance_id: int
    feed_id: int
    node_key: str
    role: PluginRole


# --- measurement events ---------------------------------------------------------------

@dataclass(frozen=True)
class RequestRecord:
    """
    One measured API call. ``status_code == 0`` means no HTTP response
    (timeout / connection error).
    """
    endpoint_class: str  # "create" | "poll" | "list" | "delete" | "health"
    method: str
    status_code: int
    latency_ms: float
    ok: bool
    t: float
    error: Optional[str] = None


@dataclass
class StatusTimeline:
    """
    Client-observed status history for one plugin instance. CUBE keeps no
    transition history (start/end dates are overwritten), so the poller records the
    wall-clock time each status was *first seen*; resolution = poll cadence.
    """
    instance_id: int
    node_key: str
    role: Optional[PluginRole]  # None for instances the poller didn't expect
    first_seen: dict[str, float] = field(default_factory=dict)
    final_status: Optional[str] = None

    def observe(self, status: str, t: float) -> None:
        if status and status not in self.first_seen:
            self.first_seen[status] = t
        if status:
            self.final_status = status


@dataclass(frozen=True)
class ResourceSample:
    t: float
    container: str
    kind: str  # "service" | "job"
    cpu_pct: float
    mem_bytes: float
    mem_limit_bytes: float
    blkio_read_bytes: float = 0.0
    blkio_write_bytes: float = 0.0
    pids: int = 0


@dataclass(frozen=True)
class QueueSample:
    """
    Depth of one Celery broker queue at time ``t`` (backpressure indicator).
    """
    t: float
    queue: str
    depth: int


# --- scenario parameterization & results ----------------------------------------------

@dataclass(frozen=True)
class ScenarioParams:
    """
    Fully-resolved parameters for a single scenario run (one repeat).
    """
    topology: str
    axis: str
    level: int
    file_count: int
    file_size: str
    depth: int
    branches: int
    layers: int
    merges: int
    feeds: int
    sleep_length: float
    poll_interval: float  # CUBE_CELERY_POLL_INTERVAL in effect (recorded)
    repeat_index: int = 0

    def scenario_id(self) -> str:
        return (
            f"{self.topology}_{self.axis}-{self.level}"
            f"_fc{self.file_count}_d{self.depth}_b{self.branches}"
            f"_L{self.layers}_feeds{self.feeds}_r{self.repeat_index}"
        )


@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    criteria: tuple[str, ...] = ()


@dataclass
class PollResult:
    """
    Facts observed while polling a scenario's feeds to completion. Policy
    (PASS/DEGRADED/FAIL) is applied separately by ``classifier``.
    """
    timelines: list[StatusTimeline]
    makespan_s: Optional[float]
    terminal: bool
    hard_failures: tuple[str, ...]
    no_progress: bool
    timed_out: bool
    final_status_counts: dict[str, int]


@dataclass
class ScenarioResult:
    params: ScenarioParams
    classification: Classification
    makespan_s: Optional[float]
    feeds: list[FeedRef]
    timelines: list[StatusTimeline]
    red: dict
    resources: dict
    db_deltas: dict
    started_at: float
    ended_at: float
    queues: dict = field(default_factory=dict)  # broker queue depth rollup
    notes: list[str] = field(default_factory=list)


@dataclass
class LevelResult:
    """
    Aggregate of the R repeats run at one escalation level.
    """
    topology: str
    axis: str
    level: int
    verdict: Verdict
    criteria: tuple[str, ...]
    repeats: list[ScenarioResult]


@dataclass(frozen=True)
class BreakingPoint:
    topology: str
    axis: str
    level: int
    criteria: tuple[str, ...]


# --- persisted runs (read side) ---------------------------------------------------------

@dataclass(frozen=True)
class RunData:
    """
    A persisted benchmark run loaded read-only (produced by ``results.load_run``,
    consumed by ``compare``). ``levels`` keeps the tidy ``levels.jsonl`` row dicts —
    they are already the cross-run contract.
    """
    run_id: str
    path: Path
    environment: dict
    summary: dict
    levels: list[dict]
