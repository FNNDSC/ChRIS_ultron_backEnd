# Benchmark harness image. The package source is bind-mounted at /app/benchmarks by the
# compose override, so this image only needs Python and the harness dependencies.
FROM docker.io/library/python:3.12-slim

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Default command is informational; `just bench-run` overrides it with the real CLI.
CMD ["python", "-m", "benchmarks.run_bench", "--help"]
