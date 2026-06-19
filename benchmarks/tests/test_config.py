"""
Tests for benchmarks.config — matrix/tier loading and the workload fingerprint.
"""

from dataclasses import replace

import pytest

from benchmarks.config import load_tier, step_for, tier_fingerprint


# -- tier loading ----------------------------------------------------------------------

def test_load_tier_smoke():
    t = load_tier("smoke")
    assert t.name == "smoke"
    assert "linear" in t.topology_axes
    assert t.repeat >= 1
    assert t.baseline.file_size == "1KiB"


def test_load_tier_missing_raises():
    with pytest.raises(KeyError):
        load_tier("nonexistent-tier")


def test_load_tier_rejects_non_escalatable_axis(tmp_path):
    p = tmp_path / "m.yml"
    p.write_text(
        "tiers:\n"
        "  bad:\n"
        "    baseline: {file_count: 1, file_size: 1KiB, depth: 1, branches: 1, "
        "layers: 1, merges: 1, feeds: 1, sleep_length: 0}\n"
        "    thresholds: {healthcheck_timeout_s: 1, api_request_timeout_s: 1, "
        "api_p95_latency_ms: 1, no_progress_timeout_s: 1, scenario_timeout_s: 1}\n"
        "    topologies:\n"
        "      linear: {axes: {bogus: 4}}\n"
    )
    with pytest.raises(ValueError):
        load_tier("bad", p)


def test_step_for_decade_only_for_file_count():
    assert step_for("file_count") == 10
    assert step_for("depth") == 2
    assert step_for("feeds") == 2
    assert step_for("branches") == 2


def test_tiers_define_quiesce_timeout():
    for name in ("smoke", "default", "full", "aging-grow", "aging-probe"):
        assert load_tier(name).thresholds.quiesce_timeout_s > 0


def test_aging_tiers_shape():
    grow, probe = load_tier("aging-grow"), load_tier("aging-probe")
    assert grow.topology_axes == {"linear": {"feeds": 4}}
    assert grow.baseline.file_count == 1000
    assert probe.topology_axes == {"linear": {"depth": 1}}   # fixed 2-instance probe


def test_headline_tier_removed():
    with pytest.raises(KeyError):
        load_tier("headline")


def test_full_linear_feeds_is_the_marquee_and_merges_escalated():
    # headline folded into full: the linear feeds axis reaches the old headline cap,
    # and fanout_fanin now escalates merges (the issue asks to iterate merges too)
    t = load_tier("full")
    assert t.topology_axes["linear"]["feeds"] == 128
    assert t.topology_axes["fanout_fanin"]["merges"] == 8


# -- workload fingerprint --------------------------------------------------------------

def test_tier_fingerprint_is_stable_and_workload_sensitive():
    t = load_tier("smoke")
    fp = tier_fingerprint(t)
    assert fp["workload_sha256"] == tier_fingerprint(load_tier("smoke"))["workload_sha256"]
    heavier = replace(t, baseline=replace(t.baseline, file_count=99))
    assert tier_fingerprint(heavier)["workload_sha256"] != fp["workload_sha256"]


def test_tier_fingerprint_hash_ignores_thresholds_and_repeat():
    t = load_tier("smoke")
    softer = replace(t, repeat=99,
                     thresholds=replace(t.thresholds, scenario_timeout_s=1))
    fp = tier_fingerprint(softer)
    assert fp["workload_sha256"] == tier_fingerprint(t)["workload_sha256"]
    assert fp["repeat"] == 99                          # recorded, just not hashed


def test_tier_fingerprint_canonicalizes_numeric_types():
    # YAML loads sleep_length: 0 as int; the CLI override produces float 0.0 —
    # equal workloads must hash equally regardless of the numeric type
    t = load_tier("smoke")
    as_int = replace(t, baseline=replace(t.baseline, sleep_length=0))
    as_float = replace(t, baseline=replace(t.baseline, sleep_length=0.0))

    assert (tier_fingerprint(as_int)["workload_sha256"]
            == tier_fingerprint(as_float)["workload_sha256"])
    
    # non-integral floats remain distinct workloads
    half = replace(t, baseline=replace(t.baseline, sleep_length=0.5))
    assert (tier_fingerprint(half)["workload_sha256"]
            != tier_fingerprint(as_int)["workload_sha256"])


def test_load_tier_coerces_baseline_types():
    t = load_tier("smoke")
    assert isinstance(t.baseline.sleep_length, float)   # YAML int -> float at the source
    assert isinstance(t.baseline.file_size, str)
