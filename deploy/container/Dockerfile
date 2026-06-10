FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/python -m pip install \
        fastmcp \
        fastapi \
        "uvicorn[standard]" \
        chromadb \
        pydantic \
        pyyaml \
        sentence-transformers \
    && /opt/venv/bin/python -m pip install -e /app/mempalace-develop

ENV PATH="/opt/venv/bin:${PATH}" \
    ASTELL_LIBRARY_ROOT=/app \
    MEMPALACE_SRC=/app/mempalace-develop \
    MEMPALACE_DB=/data/mempalace_db \
    ASTELL_KNOWLEDGE_LIBRARY=/data/Library \
    ASTELL_COMM_BUFFER=/data/COMM_BUFFER \
    ASTELL_CONTROL_DB=/data/mempalace_db/astell_control.db \
    ASTELL_UI_HOST=0.0.0.0 \
    ASTELL_UI_PORT=8080 \
    ASTELL_OPEN_BROWSER=0

COPY deploy/container/docker-entrypoint.sh /usr/local/bin/astell-docker-entrypoint
RUN chmod +x /usr/local/bin/astell-docker-entrypoint

EXPOSE 8080

ENTRYPOINT ["astell-docker-entrypoint"]
CMD ["python", "/app/mcp_ui_server.py"]
