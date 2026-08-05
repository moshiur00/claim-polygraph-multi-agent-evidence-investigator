FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLAIM_POLYGRAPH_API_HOST=0.0.0.0 \
    CLAIM_POLYGRAPH_API_PORT=8000 \
    CLAIM_POLYGRAPH_DATA_DIR=/app/data \
    CLAIM_POLYGRAPH_ORCHESTRATOR=langgraph

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["claim-polygraph-api"]
