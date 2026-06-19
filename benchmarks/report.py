"""
Render the run summary into a ticket-ready ``report.md`` (pure transform).

Reads the aggregated ``summary`` dict plus the per-level rows the runner appended to
``levels.jsonl`` and emits Markdown: the environment manifest, the breaking-point table,
and per-axis approach-to-failure curves (also available as tidy CSV).
"""

from __future__ import annotations

from typing import Iterable


def render(summary: dict, levels: list[dict]) -> str:
    env = summary.get("environment", {})
    lines: list[str] = []
    lines += _header(summary, env)
    lines += _breaking_points(summary.get("breaking_points", []))
    lines += _approach_curves(levels)
    lines += _environment_section(env)
    return "\n".join(lines) + "\n"


def render_levels_csv(levels: list[dict]) -> str:
    cols = ["topology", "axis", "level", "verdict", "makespan_median_s", "makespan_max_s",
            "worst_p95_ms", "errors", "status_5xx", "completed", "criteria"]
    
    rows = [",".join(cols)]
    
    for lv in levels:
        rows.append(",".join(csv_cell(lv.get(c)) for c in cols))
    return "\n".join(rows) + "\n"


# -- sections --------------------------------------------------------------------------

def _header(summary: dict, env: dict) -> list[str]:
    git = env.get("git", {})

    return [
        "# CUBE Load & Scalability Benchmark — Report",
        "",
        f"**Run:** {summary.get('run_id', '?')}  •  "
        f"**Tier:** {summary.get('tier', '?')}  •  "
        f"**Storage:** {env.get('storage_mode', '?')}  •  "
        f"**Commit:** {git.get('commit', '?')} (dirty: {git.get('dirty', '?')})",
        "",
        f"Levels run: {summary.get('levels_run', 0)}  •  "
        f"Breaking points: {len(summary.get('breaking_points', []))}",
        "",
    ]


def _breaking_points(bps: list[dict]) -> list[str]:
    out = ["## Breaking points", ""]
    
    if not bps:
        out += ["_No hard failure reached within the configured caps._", ""]
        return out
    
    out += markdown_table(
        ["Topology", "Axis", "Broke at level", "Criteria"],
        [[bp.get("topology"), bp.get("axis"), bp.get("level"),
          "; ".join(bp.get("criteria", []))] for bp in bps])
    
    out.append("")
    return out


def _approach_curves(levels: list[dict]) -> list[str]:
    out = ["## Approach to failure (per axis)", "",
           "_CPU% is relative to one host core (100% = one core); judge saturation "
           "against each service's `cpus` limit in the envelope, not against 100%._",
           ""]
    
    for (topology, axis), rows in _group_by_axis(levels).items():
        out.append(f"### {topology} — {axis}")
        out.append("")

        out += markdown_table(
            ["Level", "Verdict", "Makespan p50 (s)", "Worst p95 (ms)", "5xx",
             "Completed", "Criteria"],
            [[r.get("level"), r.get("verdict"), r.get("makespan_median_s"),
              r.get("worst_p95_ms"), r.get("status_5xx"), r.get("completed"),
              "; ".join(r.get("criteria", []))] for r in rows])
        
        out.append("")
        out += _peak_cpu_note(rows)
        out += _peak_io_note(rows)
    return out


def _peak_cpu_note(rows: list[dict]) -> list[str]:
    """
    Highlight which service was hottest at the highest level reached. Ephemeral
    plugin-job containers are collapsed into one aggregate so the line stays readable.
    """
    last = rows[-1] if rows else {}
    peak = last.get("peak_cpu_pct", {})

    if not peak:
        return []
    
    hottest = max(peak.items(), key=lambda kv: kv[1])
    job = last.get("peak_job_cpu_pct")
    job_suffix = f"; plugin-jobs peak {job}%" if job else ""

    return [f"_Peak CPU at level {last.get('level')}: "
            f"{hottest[0]} {hottest[1]}% (per service: {peak}){job_suffix}_", ""]


def _peak_io_note(rows: list[dict]) -> list[str]:
    """
    Highlight the heaviest disk writer at the highest level reached — the USE
    saturation signal (e.g. db WAL or the storage volume). Block I/O is measured, not
    capped, so a disk-bound breaking point is visible here without an envelope limit.
    """
    last = rows[-1] if rows else {}
    writes = {k: v for k, v in (last.get("peak_write_bytes") or {}).items() if v}
    
    if not writes:
        return []
    
    hottest = max(writes.items(), key=lambda kv: kv[1])
    pretty = {k: _human_bytes(v) for k, v in writes.items()}
    
    return [f"_Peak disk write at level {last.get('level')}: "
            f"{hottest[0]} {_human_bytes(hottest[1])} (per service: {pretty})_", ""]


def _human_bytes(n: int) -> str:
    size = float(n or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def _environment_section(env: dict) -> list[str]:
    host = env.get("host", {})
    envelope = env.get("envelope", {})
    noise = env.get("noise_floor", {})
    out = ["## Environment", ""]

    out += markdown_table(["Field", "Value"], [
        ["Host OS", host.get("operating_system")],
        ["Kernel", host.get("kernel_version")],
        ["Arch", host.get("architecture")],
        ["Host CPUs", host.get("ncpu")],
        ["Host memory (bytes)", host.get("mem_total_bytes")],
        ["Docker root", host.get("docker_root_dir")],
        ["Engine", env.get("docker", {}).get("engine_version")],
        ["API auth", _auth_cell(env.get("api_auth_mode"))],
        ["Noise floor (health p50/p95 ms)",
         f"{(noise or {}).get('health_p50_ms')} / {(noise or {}).get('health_p95_ms')}"],
    ])

    out.append("")
    out += ["### Envelope (recorded knobs)", ""]
    out += markdown_table(["Knob", "Value"], [[k, v] for k, v in envelope.items()])
    
    plugins = env.get("workload_plugins", {})
    if plugins:
        out.append("")
        out += ["### Workload plugins", ""]
        out += markdown_table(
            ["Role", "Plugin", "Version", "Installed versions"],
            [[role, p.get("name"), p.get("version"), p.get("matches")]
             for role, p in plugins.items()])

    out.append("")
    out += ["### Manual fields (fill in)", ""]
    
    for k, v in env.get("manual_fields", {}).items():
        out.append(f"- **{k}:** {v}")

    out.append("")
    return out


# -- helpers (shared with ``compare``) ---------------------------------------------------

def markdown_table(headers: "list[str]", rows: "list[list]") -> list[str]:
    """
    A GFM table as a list of lines; ``None`` cells render as an em dash, and pipes
    and newlines in cell values are escaped so they cannot break the table.
    """
    def cell(value) -> str:
        if value is None:
            return "—"
        return str(value).replace("\n", " ").replace("|", "\\|")

    out = ["| " + " | ".join(cell(h) for h in headers) + " |",
           "|" + "---|" * len(headers)]
    
    for row in rows:
        out.append("| " + " | ".join(cell(v) for v in row) + " |")
    return out


def csv_cell(value) -> str:
    """
    One RFC 4180 CSV cell; lists join with '; ', embedded quotes are doubled.
    """
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value)

    text = "" if value is None else str(value)

    if "," in text or '"' in text or "\n" in text:
        return '"' + text.replace('"', '""') + '"'
    return text


def _auth_cell(mode) -> str:
    if mode == "token":
        return "token"
    
    if mode == "basic":
        return ("basic — **degraded run**: every measured latency includes CUBE's "
                "per-request password hashing")
    return str(mode)


def _group_by_axis(levels: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    
    for lv in levels:
        grouped.setdefault((lv.get("topology"), lv.get("axis")), []).append(lv)
    
    for rows in grouped.values():
        rows.sort(key=lambda r: r.get("level", 0))
    return grouped


def main(argv: list[str] | None = None) -> int:
    """Re-render report.md + levels.csv from a results run directory (for `bench-report`)."""
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Re-render a benchmark report")
    ap.add_argument("run_dir", help="path to results/<run_id>")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    levels_path = run_dir / "levels.jsonl"
    levels = [json.loads(line) for line in
              (levels_path.read_text().splitlines() if levels_path.exists() else [])
              if line.strip()]
    
    (run_dir / "report.md").write_text(render(summary, levels))
    (run_dir / "levels.csv").write_text(render_levels_csv(levels))
    
    print(f"rewrote {run_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
