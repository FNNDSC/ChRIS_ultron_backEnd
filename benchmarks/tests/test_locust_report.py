"""
Tests for the Locust control-plane report renderer (pure CSV -> Markdown transform).
"""

from benchmarks.locust_report import _agg, _f, _users, render

STATS_HEADER = "Type,Name,Request Count,Failure Count,Requests/s,50%,95%,99%\n"


def _write_stats(path, rows):
    """rows: list of (name, count, fails, rps, p50, p95, p99)."""
    with open(path, "w") as fh:
        fh.write(STATS_HEADER)
        for r in rows:
            fh.write("GET," + ",".join(str(x) for x in r) + "\n")


def _write_failures(path, rows):
    """rows: list of (name, error, occurrences)."""
    with open(path, "w") as fh:
        fh.write("Method,Name,Error,Occurrences\n")
        for name, err, occ in rows:
            fh.write(f"GET,{name},{err},{occ}\n")


# -- pure helpers ------------------------------------------------------------------------

def test_users_matches_stats_and_failures():
    assert _users("read_u400_stats.csv") == 400
    assert _users("read_u100_failures.csv") == 100      # the bug fix: must match failures too
    assert _users("write_clean_u10_stats.csv") == 10
    assert _users("run_stats.csv") == 0


def test_f_coerces_blanks_and_numbers():
    assert _f("") == 0.0 and _f(None) == 0.0 and _f("12.5") == 12.5


def test_agg_prefers_aggregated_else_last_row(tmp_path):
    p = tmp_path / "read_u50_stats.csv"
    _write_stats(p, [("list-feeds", 100, 0, 50, 10, 30, 40),
                     ("Aggregated", 200, 2, 90, 12, 35, 50)])
    assert _agg(str(p))["Name"] == "Aggregated"
    p2 = tmp_path / "read_u25_stats.csv"
    _write_stats(p2, [("list-feeds", 7, 0, 9, 1, 2, 3)])    # no Aggregated row
    assert _agg(str(p2))["Request Count"] == "7"            # falls back to last row


# -- rendering ---------------------------------------------------------------------------

def test_saturation_sweep_sorted_with_fail_pct(tmp_path):
    _write_stats(tmp_path / "read_u50_stats.csv", [("Aggregated", 1000, 20, 117, 32, 110, 520)])
    _write_stats(tmp_path / "read_u25_stats.csv", [("Aggregated", 500, 0, 67, 22, 61, 190)])
    md = render(str(tmp_path))
    assert "## Read-only saturation sweep" in md
    i25, i50 = md.index("| 25 |"), md.index("| 50 |")
    assert i25 < i50                                        # ascending by users
    assert "| 50 | 1000 | 20 | 2.0% | 117 | 32 | 110 | 520 |" in md


def test_top_failures_uses_highest_level(tmp_path):
    _write_stats(tmp_path / "read_u50_stats.csv", [("Aggregated", 10, 1, 5, 1, 2, 3)])
    _write_stats(tmp_path / "read_u400_stats.csv", [("Aggregated", 10, 9, 5, 1, 2, 3)])
    _write_failures(tmp_path / "read_u50_failures.csv", [("list-feeds", "HTTP 500", 5)])
    _write_failures(tmp_path / "read_u400_failures.csv", [("list-instances", "HTTP 500", 919)])
    md = render(str(tmp_path))
    assert "Top failures (read_u400_failures.csv)" in md    # highest level, not u50
    assert "919" in md and "read_u50_failures" not in md


def test_generic_run_table_rendered(tmp_path):
    # the recipe's default `--csv .../run` must still produce a real report (R1 regression)
    _write_stats(tmp_path / "run_stats.csv", [("create-instance", 97, 0, 1, 62, 140, 150),
                                              ("Aggregated", 97, 0, 1, 62, 140, 150)])
    md = render(str(tmp_path))
    assert "## Ad-hoc run" in md and "create-instance" in md


def test_empty_dir_is_header_only(tmp_path):
    md = render(str(tmp_path))
    assert md.startswith("# CUBE Control-Plane RED")
    assert "## Read-only saturation sweep" not in md and "## Top failures" not in md
