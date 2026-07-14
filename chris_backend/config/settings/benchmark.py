"""
Benchmark settings: the development stack with a production-like, *recorded* envelope.

Identical to ``local`` except the artificially tiny dev DB connection pool is made an
explicit, env-driven knob. The benchmark measures CUBE's architecture capacity, so the
pool, the number of uvicorn workers (set on the ``chris`` service's command), and Postgres
``max_connections`` (set on the ``db`` service's command) are all pinned in
``docker-compose.benchmark.yml`` and recorded in every report.

Normal development is unaffected — only the benchmark compose profile selects this module.
"""

import os

from .local import *  # noqa: F401,F403


options = DATABASES['default'].setdefault('OPTIONS', {})
options['pool'] = {
    'min_size': int(os.getenv('CUBE_DB_POOL_MIN_SIZE', '2')),
    'max_size': int(os.getenv('CUBE_DB_POOL_MAX_SIZE', '10')),
    'timeout': int(os.getenv('CUBE_DB_POOL_TIMEOUT', '10')),
}
