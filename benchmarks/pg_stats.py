"""
Per-scenario ``pg_stat_statements`` snapshots (best-effort).

Turns "db CPU at 210%" into named queries: the runner resets the statement stats at
scenario start and snapshots every statement recorded since, most total execution time
first, persisting them under ``scenarios/<id>/pg_stats.json``. Keeping all of them, not
just the expensive ones, is what lets a run show that a cheap statement no longer runs.

Runs ``psql`` *inside* the db container via the Docker socket (no client-side
postgres dependency); credentials come from the container's own ``POSTGRES_*`` env.
Requires ``shared_preload_libraries=pg_stat_statements`` — the benchmark compose sets
it — and degrades to unavailable (with the reason recorded once) otherwise.

``connection_states`` uses the same access for ``pg_stat_activity``: how many connections
each client holds and in which state, which tells idle pooled connections apart from ones
left ``idle in transaction``.
"""

from __future__ import annotations

from typing import Optional

from .docker_client import DockerClient


STATEMENTS_SQL = (
    "SELECT calls, round(total_exec_time)::bigint AS total_ms, "
    "round(mean_exec_time::numeric, 2) AS mean_ms, rows, "
    "left(regexp_replace(query, '\\s+', ' ', 'g'), 300) AS query "
    "FROM pg_stat_statements "
    "WHERE query NOT ILIKE '%pg_stat_statements%' "
    "ORDER BY total_exec_time DESC"
)

CONNECTION_STATES_SQL = (
    "SELECT coalesce(host(client_addr), 'local'), coalesce(state, 'unknown'), count(*) "
    "FROM pg_stat_activity "
    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
    "GROUP BY 1, 2 ORDER BY 1, 2"
)


def parse_psql_rows(output: str, columns: tuple[str, ...]) -> list[dict]:
    """
    Parse ``psql -At -F<tab>`` output into row dicts (numeric where possible).
    """
    rows = []

    for line in output.splitlines():
        parts = line.split("\t")

        if len(parts) != len(columns):
            continue

        row = {}
        for name, value in zip(columns, parts):
            try:
                row[name] = int(value)
            except ValueError:
                try:
                    row[name] = float(value)
                except ValueError:
                    row[name] = value

        rows.append(row)
    return rows


def psql(docker: DockerClient, sql: str, *, service: str = "db",
         env: Optional[dict] = None) -> "tuple[int, str]":
    """
    Run one statement with ``psql -At -F<tab>`` inside the db container, as its own
    ``POSTGRES_USER`` on its ``POSTGRES_DB`` (read from ``env``, else the container).
    """
    env = docker.service_env(service) if env is None else env

    return docker.exec_in_service(
        service, ["psql", "-U", env.get("POSTGRES_USER", "chris"),
                  "-d", env.get("POSTGRES_DB", "chris_dev"), "-At", "-F", "\t", "-c", sql])


def connection_states(docker: DockerClient, service: str = "db") -> list[dict]:
    """
    Connections to the database by client address and state; [] when psql cannot run.
    """
    code, out = psql(docker, CONNECTION_STATES_SQL, service=service)

    if code != 0:
        return []
    return parse_psql_rows(out, ("client_addr", "state", "count"))


class PgStatStatements:
    """
    Reset/snapshot interface over the db container; no-op when unavailable.
    """

    def __init__(self, docker: DockerClient, service: str = "db"):
        self._docker = docker
        self._service = service
        self.unavailable_reason: Optional[str] = None

        self._env = docker.service_env(service)
        
        code, out = self._psql("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
        
        if code != 0:
            # most commonly: shared_preload_libraries not set (base dev compose)
            self.unavailable_reason = out.strip()[:300] or f"psql exit {code}"

    @property
    def available(self) -> bool:
        return self.unavailable_reason is None

    def reset(self) -> None:
        if self.available:
            self._psql("SELECT pg_stat_statements_reset()")

    def snapshot(self, limit: Optional[int] = None) -> list[dict]:
        """
        Statements since the last reset, most total execution time first: all of them
        unless ``limit`` is given. Two kinds of statement can still be missing: entries
        evicted by ``pg_stat_statements.max`` (5,000 by default), and statements that
        failed with an error, which ``pg_stat_statements`` never records.
        """
        if not self.available:
            return []

        sql = STATEMENTS_SQL if limit is None else f"{STATEMENTS_SQL} LIMIT {int(limit)}"
        code, out = self._psql(sql)

        if code != 0:
            return []
        return parse_psql_rows(out, ("calls", "total_ms", "mean_ms", "rows", "query"))

    def _psql(self, sql: str) -> "tuple[int, str]":
        return psql(self._docker, sql, service=self._service, env=self._env)
