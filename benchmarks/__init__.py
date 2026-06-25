"""
CUBE load & scalability benchmark harness (v1, data plane).

See ``benchmarks/STRATEGY.md`` for the design rationale. The package is organized
as small single-responsibility modules: pure logic (``units``, ``topologies``,
``classifier``, ``metrics``, ``escalation``) is separated from side-effecting
adapters (``chris_api``, ``docker_client``, ``stats_sampler``, ``executor``,
``poller``, ``environment``, ``recovery``), and everything is wired together only
in the composition root (``run_bench``).
"""
