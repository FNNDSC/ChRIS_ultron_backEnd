"""
Tests for benchmarks.results — JSON encoding and the run store/loader.
"""

import json
from pathlib import Path

import pytest

from benchmarks.models import Classification, Verdict
from benchmarks.results import (ResultsStore, find_runs, load_run, resolve_run,
                                to_json)


# -- to_json ---------------------------------------------------------------------------

def test_to_json_enum():
    assert json.loads(to_json(Verdict.PASS)) == "PASS"


def test_to_json_dataclass_with_nested_enum_and_tuple():
    d = json.loads(to_json(Classification(Verdict.FAIL, ("no_progress",))))
    assert d["verdict"] == "FAIL"
    assert d["criteria"] == ["no_progress"]


def test_to_json_path():
    assert json.loads(to_json(Path("/a/b"))) == "/a/b"


def test_to_json_rejects_unknown_type():
    with pytest.raises(TypeError):
        to_json(object())


# -- load_run / find_runs --------------------------------------------------------------

def test_load_run_round_trips_the_store(tmp_path):
    # the writer builds the fixture the reader consumes -> layout tested end to end
    store = ResultsStore(tmp_path, run_id="R1")
    store.write_json("summary.json", {"run_id": "R1", "breaking_points": []})
    store.write_json("environment.json", {"storage_mode": "fslink"})
    store.append_jsonl("levels.jsonl",
                       [{"topology": "linear", "axis": "depth", "level": 1}])
    run = load_run(store.run_dir)
    assert run.run_id == "R1" and run.path == store.run_dir
    assert run.environment["storage_mode"] == "fslink"
    assert run.levels[0]["level"] == 1


def test_load_run_requires_summary(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_run(tmp_path)


def test_load_run_tolerates_missing_optional_files(tmp_path):
    store = ResultsStore(tmp_path, run_id="R2")
    store.write_json("summary.json", {"run_id": "R2"})
    run = load_run(store.run_dir)
    assert run.environment == {} and run.levels == []


def test_find_runs_newest_first_and_skips_non_runs(tmp_path):
    for rid in ("2026-01-01T000000Z", "2026-02-01T000000Z"):
        ResultsStore(tmp_path, run_id=rid).write_json("summary.json", {"run_id": rid})
    (tmp_path / "not-a-run").mkdir()
    assert [p.name for p in find_runs(tmp_path)] == \
        ["2026-02-01T000000Z", "2026-01-01T000000Z"]


def test_find_runs_spans_multiple_roots(tmp_path):
    live, history = tmp_path / "results", tmp_path / "history"
    ResultsStore(live, run_id="2026-02-01T000000Z").write_json("summary.json", {})
    ResultsStore(history, run_id="2026-01-01T000000Z").write_json("summary.json", {})
    assert [p.name for p in find_runs(live, history, tmp_path / "missing-root")] == \
        ["2026-02-01T000000Z", "2026-01-01T000000Z"]


def test_load_run_falls_back_to_environment_embedded_in_summary(tmp_path):
    # archived/old runs may lack environment.json; the runner embeds env in summary
    store = ResultsStore(tmp_path, run_id="R3")
    store.write_json("summary.json",
                     {"run_id": "R3", "environment": {"storage_mode": "fslink"}})
    run = load_run(store.run_dir)
    assert run.environment == {"storage_mode": "fslink"}


# -- resolve_run -----------------------------------------------------------------------

def test_resolve_run_prefers_explicit_path_then_results_then_history(tmp_path):
    live, history = tmp_path / "results", tmp_path / "history"
    roots = (live, history)
    ResultsStore(live, run_id="in-results").write_json("summary.json", {})
    ResultsStore(history, run_id="in-history").write_json("summary.json", {})
    ResultsStore(live, run_id="in-both").write_json("summary.json", {})
    ResultsStore(history, run_id="in-both").write_json("summary.json", {})

    explicit = ResultsStore(tmp_path, run_id="explicit").run_dir
    ResultsStore(tmp_path, run_id="explicit").write_json("summary.json", {})

    assert resolve_run(str(explicit), roots) == explicit          # path wins
    assert resolve_run("in-results", roots) == live / "in-results"
    assert resolve_run("in-history", roots) == history / "in-history"
    assert resolve_run("in-both", roots) == live / "in-both"      # results before history


def test_resolve_run_not_found_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="no-such-run"):
        resolve_run("no-such-run", (tmp_path,))
