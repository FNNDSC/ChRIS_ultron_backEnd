"""
Tests for benchmarks.report — Markdown/CSV rendering of a run.
"""

from benchmarks.report import csv_cell, markdown_table, render, render_levels_csv


# -- fixtures --------------------------------------------------------------------------

def _level(**kw):
    base = dict(topology="linear", axis="depth", level=1, verdict="PASS", criteria=[],
                makespan_median_s=1.0, makespan_max_s=1.0, worst_p95_ms=10, errors=0,
                status_5xx=0, completed=2, peak_cpu_pct={"db": 50.0})
    base.update(kw)
    return base


# -- render ----------------------------------------------------------------------------

def test_render_has_sections_and_breaking_point():
    summary = {"run_id": "R", "tier": "smoke", "environment": {}, "levels_run": 2,
               "breaking_points": [{"topology": "linear", "axis": "depth", "level": 2,
                                    "criteria": ["no_progress"]}]}
    md = render(summary, [_level(),
                          _level(level=2, verdict="FAIL", criteria=["no_progress"])])
    assert "Breaking points" in md
    assert "Approach to failure" in md
    assert "no_progress" in md


def test_render_shows_aggregate_job_cpu_and_disk_write():
    summary = {"run_id": "R", "tier": "full", "environment": {}, "levels_run": 1,
               "breaking_points": []}
    lv = _level(peak_cpu_pct={"db": 70.0}, peak_job_cpu_pct=250.0,
                peak_write_bytes={"db": 2048})
    md = render(summary, [lv])
    assert "plugin-jobs peak 250.0%" in md              # jobs collapsed to one number
    assert "Peak disk write" in md
    assert "2.0 KiB" in md                              # bytes rendered human-readable


def test_peak_io_note_skips_zero_write_services():
    summary = {"run_id": "R", "tier": "full", "environment": {}, "levels_run": 1,
               "breaking_points": []}
    
    # every service wrote nothing -> no disk-write line at all (the fslink common case)
    md = render(summary, [_level(peak_write_bytes={"db": 0, "chris": 0})])
    assert "Peak disk write" not in md
    
    # mixed -> only the non-zero writer is rendered (zeros filtered out)
    md2 = render(summary, [_level(peak_write_bytes={"db": 1048576, "chris": 0})])
    assert "Peak disk write" in md2 and "db 1.0 MiB" in md2
    assert "chris" not in md2                           # zero-write service omitted


def test_human_bytes_unit_boundaries():
    from benchmarks.report import _human_bytes
    assert _human_bytes(0) == "0 B"
    assert _human_bytes(512) == "512 B"
    assert _human_bytes(2048) == "2.0 KiB"
    assert _human_bytes(5 * 1024 * 1024) == "5.0 MiB"
    assert _human_bytes(3 * 1024 ** 3) == "3.0 GiB"


def test_render_flags_degraded_basic_auth():
    summary = {"run_id": "R", "tier": "smoke", "levels_run": 0, "breaking_points": [],
               "environment": {"api_auth_mode": "basic"}}
    md = render(summary, [])
    assert "degraded run" in md                       # basic auth must be loud
    summary["environment"]["api_auth_mode"] = "token"
    assert "degraded run" not in render(summary, [])


# -- markdown_table & csv --------------------------------------------------------------

def test_markdown_table_shape_dashes_and_escaping():
    lines = markdown_table(["A", "B"], [[1, None], ["x|y", "p\nq"]])
    assert lines[0] == "| A | B |"
    assert lines[1] == "|---|---|"
    assert lines[2] == "| 1 | — |"                       # None renders as em dash
    assert lines[3] == "| x\\|y | p q |"                 # pipes escaped, newlines spaced


def test_render_workload_plugins_table():
    summary = {"run_id": "R", "tier": "smoke", "levels_run": 0, "breaking_points": [],
               "environment": {"workload_plugins": {
                   "fs": {"name": "dbg-bigfiles", "version": "1.0.0", "id": 1,
                          "dock_image": "localhost/dbg-bigfiles", "matches": 1},
                   "ts": {"name": "pl-topologicalcopy", "version": "1.0.13", "id": 6,
                          "dock_image": "fnndsc/pl-topologicalcopy", "matches": 1}}}}
    md = render(summary, [])
    assert "### Workload plugins" in md
    assert "pl-topologicalcopy" in md and "1.0.13" in md   # resolved version in the report
    assert "Installed versions" in md                       # ambiguity (matches) column


def test_render_omits_workload_plugins_when_absent():
    summary = {"run_id": "R", "tier": "smoke", "levels_run": 0, "breaking_points": [],
               "environment": {}}
    assert "Workload plugins" not in render(summary, [])     # back-compat for old runs


def test_csv_cell_rfc4180_quoting():
    assert csv_cell("plain") == "plain"
    assert csv_cell("a,b") == '"a,b"'
    assert csv_cell('he said "hi"') == '"he said ""hi"""'      # embedded quotes doubled
    # a criteria list joins with "; " (no comma) -> no quoting needed
    assert csv_cell(["no_progress", "api_5xx:1"]) == "no_progress; api_5xx:1"


def test_render_levels_csv_header_and_rows():
    csv = render_levels_csv([_level(), _level(level=2, verdict="FAIL",
                                              criteria=["a,b"])])
    lines = csv.splitlines()
    assert lines[0].startswith("topology,axis,level,verdict")
    assert len(lines) == 3
    assert '"a,b"' in lines[2]                          # criteria with comma is quoted
