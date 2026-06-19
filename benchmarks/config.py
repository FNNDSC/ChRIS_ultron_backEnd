"""
Typed benchmark configuration and the ``matrix.yml`` loader (no logic).

A *tier* (smoke / default / full, plus the aging-grow / aging-probe pair) defines a
baseline workload, the escalation axes per topology (with binary caps), repetition
count, failure thresholds and the poll cadence. The escalation engine walks
``topology_axes``; the runner overrides the matching baseline field with the current
level to build a ``ScenarioParams``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml


DEFAULT_MATRIX = Path(__file__).with_name("matrix.yml")

#: scenario fields an axis may escalate (must be attribute names on Baseline)
ESCALATABLE_AXES = ("depth", "branches", "layers", "merges", "feeds", "file_count")

#: escalation multiplier per axis. Most axes double (1, 2, 4, 8 …); file_count goes by
#: decade (1, 10, 100, 1000, …) per the issue ("Varying file count- 1, 10, 100, etc.").
AXIS_STEP = {"file_count": 10}


def step_for(axis: str) -> int:
    return AXIS_STEP.get(axis, 2)


@dataclass(frozen=True)
class Baseline:
    file_count: int
    file_size: str
    depth: int
    branches: int
    layers: int
    merges: int
    feeds: int
    sleep_length: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Thresholds:
    healthcheck_timeout_s: int
    api_request_timeout_s: int
    api_p95_latency_ms: int
    no_progress_timeout_s: int
    scenario_timeout_s: int
    #: max wait for async feed deletion to settle between scenarios (see recovery)
    quiesce_timeout_s: int = 300


@dataclass(frozen=True)
class Tier:
    name: str
    baseline: Baseline
    thresholds: Thresholds
    repeat: int
    poll_every_s: float
    #: topology kind -> {axis name -> cap level}
    topology_axes: dict[str, dict[str, int]]


def _canonical(value):
    """
    Normalize numeric types so equal workloads hash equally: YAML may load ``0``
    where the CLI produces ``0.0`` (json.dumps would render them differently).
    """
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def tier_fingerprint(tier: Tier) -> dict:
    """
    Canonical identity of the *effective* workload (after CLI filters/overrides),
    recorded with every run so runs can be checked for comparability later.

    ``workload`` fields change what is measured — a hash mismatch means two runs are
    not comparable. ``thresholds`` and ``repeat`` only change verdicts/statistics, so
    they are recorded alongside (compared as warnings, not blockers) but kept out of
    the hash.
    """
    workload = _canonical({
        "baseline": tier.baseline.as_dict(),
        "topology_axes": tier.topology_axes,
        "axis_steps": {axis: step_for(axis)
                       for axes in tier.topology_axes.values() for axis in axes},
        "poll_every_s": tier.poll_every_s,
    })

    sha = hashlib.sha256(
        json.dumps(workload, sort_keys=True).encode()).hexdigest()
    
    return {
        "tier": tier.name,
        "workload": workload,
        "workload_sha256": sha,
        "thresholds": asdict(tier.thresholds),
        "repeat": tier.repeat,
    }


def load_tier(name: str, path: "str | Path | None" = None) -> Tier:
    """
    Load a single tier from a matrix YAML file.
    """
    path = Path(path) if path else DEFAULT_MATRIX
    doc = yaml.safe_load(path.read_text())
    tiers = doc.get("tiers", {})

    if name not in tiers:
        raise KeyError(f"tier {name!r} not in {path} (have: {sorted(tiers)})")
    
    raw = tiers[name]
    topology_axes: dict[str, dict[str, int]] = {}

    for topo, spec in raw["topologies"].items():
        axes = spec.get("axes", {})

        for axis in axes:
            if axis not in ESCALATABLE_AXES:
                raise ValueError(f"axis {axis!r} (topology {topo!r}) is not escalatable")
        
        topology_axes[topo] = {axis: int(cap) for axis, cap in axes.items()}

    baseline = dict(raw["baseline"])
    baseline["sleep_length"] = float(baseline["sleep_length"])   # YAML 0 vs CLI 0.0
    baseline["file_size"] = str(baseline["file_size"])

    return Tier(
        name=name,
        baseline=Baseline(**baseline),
        thresholds=Thresholds(**raw["thresholds"]),
        repeat=int(raw.get("repeat", 1)),
        poll_every_s=float(raw.get("poll_every_s", 1.0)),
        topology_axes=topology_axes,
    )
