FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gosu \
        git \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/astell-requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/python -m pip install -r /tmp/astell-requirements.txt \
    && rm -rf /root/.cache/pip /tmp/astell-requirements.txt

COPY . /app

RUN /opt/venv/bin/python -m pip install -e /app/mempalace-develop \
    && groupadd --system astell \
    && useradd --system --gid astell --home-dir /app --shell /usr/sbin/nologin astell \
    && mkdir -p /data/mempalace_db /data/Library /data/COMM_BUFFER /projects \
    && chown -R astell:astell /data /projects \
    && chmod +x /app/deploy/container/docker-entrypoint.sh

ENV PATH="/opt/venv/bin:${PATH}" \
    ASTELL_LIBRARY_ROOT=/app \
    MEMPALACE_SRC=/app/mempalace-develop \
    MEMPALACE_DB=/data/mempalace_db \
    ASTELL_KNOWLEDGE_LIBRARY=/data/Library \
    ASTELL_COMM_BUFFER=/data/COMM_BUFFER \
    ASTELL_CONTROL_DB=/data/mempalace_db/astell_control.db \
    ASTELL_UI_HOST=0.0.0.0 \
    ASTELL_UI_PORT=8080 \
    ASTELL_OPEN_BROWSER=0 \
    ASTELL_AUTH_ENABLED=1 \
    ASTELL_AUTH_USER=astell \
    ASTELL_AUTH_USERS_SHA256=""

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["/app/deploy/container/docker-entrypoint.sh"]
CMD ["python", "/app/mcp_ui_server.py"]
