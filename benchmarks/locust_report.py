"""
Render Locust control-plane CSVs into a human-readable RED report (pure transform).

The data-plane equivalent is ``report.py``; this is its control-plane counterpart. It reads
the CSVs Locust writes with ``--csv`` (``read_u<N>_stats.csv`` saturation sweep,
``write_*_stats.csv`` per-endpoint, ``*_failures.csv``) and emits a Markdown summary —
RED = Rate, Errors, Duration percentiles.

    python -m benchmarks.locust_report <csv_dir> [out.md]      # default out: <csv_dir>/report.md
"""

from __future__ import annotations

import csv
import glob
import os
import re
import sys


def _rows(path: str) -> list[dict]:
    with open(path) as fh:
        return list(csv.DictReader(fh))


def _agg(path: str) -> dict:
    rows = _rows(path)
    for r in rows:
        if r.get("Name") == "Aggregated":
            return r
    return rows[-1] if rows else {}


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _users(path: str) -> int:
    m = re.search(r"_u(\d+)_", path)   # matches both _stats.csv and _failures.csv
    return int(m.group(1)) if m else 0


def render(csv_dir: str) -> str:
    lines = [
        "# CUBE Control-Plane RED — Locust Report",
        "",
        "_Generated from Locust `--csv` output (RED = Rate, Errors, Duration percentiles). "
        "Pair with the data-plane per-run `report.md` files for the full picture._",
        "",
    ]

    reads = sorted(glob.glob(os.path.join(csv_dir, "read_u*_stats.csv")), key=_users)
    if reads:
        lines += ["## Read-only saturation sweep", "",
                  "| Users | Requests | Failures | Fail % | RPS | p50 (ms) | p95 (ms) | p99 (ms) |",
                  "|---|---|---|---|---|---|---|---|"]
        for p in reads:
            a = _agg(p)
            u = _users(p)
            rc = int(_f(a.get("Request Count")))
            fc = int(_f(a.get("Failure Count")))
            lines.append(
                f"| {u} | {rc} | {fc} | {(100 * fc / rc if rc else 0):.1f}% | "
                f"{_f(a.get('Requests/s')):.0f} | {a.get('50%', '?')} | "
                f"{a.get('95%', '?')} | {a.get('99%', '?')} |")
        lines.append("")

    # every non-sweep *_stats.csv (the recipe's default `run`, write runs, ad-hoc) rendered
    # as a per-endpoint table so a plain `just bench-locust …` still produces a real report
    labels = {"write_clean_u10": "Write-path run (u=10, healthy stack)",
              "write_u10": "Write-path run (u=10)", "run": "Ad-hoc run"}
    others = sorted(p for p in glob.glob(os.path.join(csv_dir, "*_stats.csv"))
                    if not os.path.basename(p).startswith("read_u"))
    for wp in others:
        stem = os.path.basename(wp)[:-len("_stats.csv")]
        lines += [f"## {labels.get(stem, f'Run: `{stem}`')}", "",
                  "| Endpoint | Requests | Failures | p50 (ms) | p95 (ms) |",
                  "|---|---|---|---|---|"]
        for r in _rows(wp):
            lines.append(f"| {r.get('Name')} | {r.get('Request Count')} | "
                         f"{r.get('Failure Count')} | {r.get('50%', '?')} | "
                         f"{r.get('95%', '?')} |")
        lines.append("")

    fails = sorted(glob.glob(os.path.join(csv_dir, "read_u*_failures.csv")), key=_users)
    if fails:
        fp = fails[-1]
        rows = [r for r in _rows(fp) if r.get("Error")]
        if rows:
            rows.sort(key=lambda r: -int(_f(r.get("Occurrences"))))
            lines += [f"## Top failures ({os.path.basename(fp)})", "",
                      "| Occurrences | Endpoint | Error |", "|---|---|---|"]
            for r in rows[:8]:
                lines.append(f"| {r.get('Occurrences')} | {r.get('Name')} | {r.get('Error')} |")
            lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: "list[str] | None" = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m benchmarks.locust_report <csv_dir> [out.md]")
        return 2
    csv_dir = argv[0]
    out = argv[1] if len(argv) > 1 else os.path.join(csv_dir, "report.md")
    with open(out, "w") as fh:
        fh.write(render(csv_dir))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
