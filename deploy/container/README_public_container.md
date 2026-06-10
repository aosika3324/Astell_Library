# Astell Library Public Container Deployment

This deployment is designed for public access with no registration feature.
Authentication is handled by Caddy Basic Auth before requests reach the app.

## Architecture

- `caddy`: public entrypoint on ports `80` and `443`, automatic HTTPS, Basic Auth
- `astell`: private application container, only reachable from Caddy
- Docker volumes:
  - `astell_mempalace_db`: ChromaDB and `astell_control.db`
  - `astell_library`: knowledge library and solidified memories
  - `astell_comm`: legacy task/log buffer
  - `caddy_data`: HTTPS certificates

The app container does not publish port `8080` to the internet.

## Prerequisites

1. Ubuntu 24.04 server
2. A domain name, for example `astell.example.com`
3. DNS `A` record pointing that domain to the server public IP
4. Security group/firewall allows inbound `80/tcp` and `443/tcp`

## One-command Ubuntu Deployment

From the repository root on the server:

```bash
sudo PUBLIC_HOST=astell.example.com \
  BASIC_AUTH_USER=admin \
  BASIC_AUTH_PASSWORD='change-this-strong-password' \
  ACME_EMAIL=it@example.com \
  ./deploy/container/ubuntu24_container_deploy.sh
```

Then open:

```text
https://astell.example.com/
```

The browser will ask for the username and password. There is no registration
page and no self-service signup.

## Docker Already Installed

```bash
cd deploy/container
./init_env.sh astell.example.com admin 'change-this-strong-password' it@example.com
docker compose up -d --build
```

## Generated Password Mode

If you omit `BASIC_AUTH_PASSWORD`, the script generates one and prints it once:

```bash
sudo PUBLIC_HOST=astell.example.com ./deploy/container/ubuntu24_container_deploy.sh
```

## Operations

```bash
cd deploy/container
docker compose ps
docker compose logs -f
docker compose restart
docker compose pull caddy
docker compose up -d --build
```

## Change Password

```bash
cd deploy/container
./init_env.sh astell.example.com admin 'new-strong-password' it@example.com
docker compose up -d --force-recreate caddy
```

## Shared Project Paths

The compose file mounts `deploy/container/projects` into the app as `/projects`.
For MC projects that need Astell records, place them under that folder and use
container paths such as:

```text
/projects/MyMinecraftAddon
```

The project still needs the expected `resource` and `behavior` directories.

## Security Notes

- Keep `.env` private; it contains the password hash and deployment domain.
- Use a strong password and rotate it when employees leave.
- This is shared Basic Auth, not per-user audit login.
- Do not publish the app container port directly; keep access through Caddy.
