# Astell Library Service Deployment

This is the service-oriented deployment skeleton for Astell Library.

## What It Starts

- Web UI and HTTP API: `mcp_ui_server.py` on port `8080` inside the container.
- Persistent data volumes:
  - `/data/Library`
  - `/data/mempalace_db`
  - `/data/COMM_BUFFER`
- Shared project mount:
  - host `deploy/container/projects`
  - container `/projects`
- App-level Basic Auth for direct access protection.

The stdio MCP server is still available inside the container:

```bash
docker compose exec astell python /app/mcp_server.py
```

## Local Or Single-Host Docker

From the repository root:

```bash
bash ./deploy/start_service.sh localhost astell 'change-this-strong-password'
```

On Windows PowerShell:

```powershell
.\deploy\start_service.ps1 -PublicHost localhost -User astell -Password 'change-this-strong-password'
```

Then open:

```text
http://localhost:8080/
```

If you omit the password, the script generates one and prints it once.

## Public Server With Caddy And HTTPS

Use the container deployment under `deploy/container` when this is exposed to
the public internet. It keeps the app container private and publishes only
Caddy on ports `80` and `443`.

```bash
cd deploy/container
bash ./init_env.sh astell.example.com astell 'change-this-strong-password' admin@example.com
docker compose up -d --build
```

Open:

```text
https://astell.example.com/
```

For a fresh Ubuntu 24.04 host, use:

```bash
sudo PUBLIC_HOST=astell.example.com \
  BASIC_AUTH_USER=astell \
  BASIC_AUTH_PASSWORD='change-this-strong-password' \
  ACME_EMAIL=admin@example.com \
  ./deploy/container/ubuntu24_container_deploy.sh
```

## Authentication

There are two layers:

- Caddy Basic Auth: public reverse-proxy gate, configured by `BASIC_AUTH_USER`
  and `BASIC_AUTH_HASH`.
- Astell Basic Auth: app-level fallback, configured by `ASTELL_AUTH_ENABLED`,
  `ASTELL_AUTH_USER`, and `ASTELL_AUTH_PASSWORD_SHA256`.

The helper scripts generate both hashes from the same plaintext password. Do
not commit `.env`.

## Health Checks

Unauthenticated liveness:

```bash
curl http://127.0.0.1:8080/healthz
```

Authenticated readiness:

```bash
curl -u astell:'change-this-strong-password' http://127.0.0.1:8080/readyz
```

## Operations

Root compose:

```bash
docker compose ps
docker compose logs -f astell
docker compose restart astell
docker compose up -d --build
```

Public Caddy compose:

```bash
cd deploy/container
docker compose ps
docker compose logs -f
docker compose up -d --build
```

## Notes

- Use `/projects/MyAddon` paths inside the UI when the project is mounted under
  `deploy/container/projects`.
- Keep direct port `8080` closed on public servers unless you intentionally use
  the root compose for private network access.
- This skeleton provides shared Basic Auth, not per-user accounts or audit
  login.
