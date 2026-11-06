# Compose lab image (PRD §10.1): one image for agent, mcp-legit and mcp-malicious.
# Build context is the repo root. The compose file mounts ./src read-only over
# /app/src at runtime, so code changes need no rebuild; the build only installs deps.
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -c src/manthan/modules/agent/lab-constraints.txt ".[agent,ollama]"
ENV PYTHONPATH=/app/src HOME=/tmp PYTHONUNBUFFERED=1
