# POC image for the Card Disputes Copilot fictional bank API.
# Build from the repository root:
#   docker build -f deploy/poc/Dockerfile -t ccd-poc-api:poc .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    BANK_DATA_DIR=/app/data/dev \
    BANK_STATE=/app/.state/mock.sqlite \
    BANK_PORT=8000

WORKDIR /app

# git: tools/scored_run.py shells out to git for commit provenance (falls back to
# "unknown" without a repo). script+curl: ECS Exec command logging and smoke tests.
RUN apt-get update \
 && apt-get install --no-install-recommends -y git bsdextrautils curl \
 && rm -rf /var/lib/apt/lists/*

# Pinned to the pyproject runtime dependencies so the image matches CI.
RUN pip install --no-cache-dir \
      "pydantic==2.14.1" \
      "opentelemetry-api==1.45.1" \
      "opentelemetry-sdk==1.45.1"

COPY pyproject.toml models.toml README.md ./
COPY src ./src
COPY tools ./tools
COPY evals ./evals
COPY feedback ./feedback
COPY data ./data
COPY deploy/poc ./deploy/poc

RUN useradd --create-home --uid 10001 app \
 && mkdir -p /app/.state /app/reports /app/submissions \
 && chown -R app:app /app/.state /app/reports /app/submissions

USER app
EXPOSE 8000

# The load balancer health check hits GET /health, which returns 200 + JSON.
CMD ["python", "deploy/poc/serve.py"]
