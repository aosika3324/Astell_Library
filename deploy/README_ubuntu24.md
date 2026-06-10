# Ubuntu 24.04 Deployment

This installs Astell Library as a Python virtualenv service managed by systemd.

## Quick Start

Upload or clone this repository onto the Ubuntu server, then run:

```bash
cd /path/to/Astell_Library
chmod +x deploy/ubuntu24_deploy.sh
sudo ./deploy/ubuntu24_deploy.sh
```

Default result:

- App directory: `/opt/astell-library`
- Virtualenv: `/opt/astell-library/.venv`
- Environment file: `/etc/astell-library/astell.env`
- Web service: `astell-control-tower`
- Web URL: `http://SERVER_IP:8080/`
- MCP wrapper command: `/usr/local/bin/astell-mcp-server`

## Common Options

Run on another port:

```bash
sudo ASTELL_UI_PORT=18080 ./deploy/ubuntu24_deploy.sh
```

Install behind Nginx on port 80:

```bash
sudo ENABLE_NGINX=1 SERVER_NAME=astell.internal ./deploy/ubuntu24_deploy.sh
```

Install behind Nginx with shared basic auth:

```bash
sudo ENABLE_NGINX=1 ENABLE_BASIC_AUTH=1 BASIC_AUTH_USER=astell BASIC_AUTH_PASSWORD='change-this' ./deploy/ubuntu24_deploy.sh
```

Install somewhere else:

```bash
sudo INSTALL_DIR=/srv/astell-library ASTELL_UI_PORT=8080 ./deploy/ubuntu24_deploy.sh
```

## Operations

```bash
sudo systemctl status astell-control-tower
sudo journalctl -u astell-control-tower -f
sudo systemctl restart astell-control-tower
```

Health check:

```bash
curl http://127.0.0.1:8080/api/status
```

## MCP Usage

Use this command in MCP clients that can run a stdio server on the Ubuntu host:

```bash
/usr/local/bin/astell-mcp-server
```

The wrapper loads `/etc/astell-library/astell.env`, so MCP and the web UI share
the same `Library`, `mempalace_db`, and runtime paths.

## Notes

This script is intended for trusted company intranet use. For public internet
exposure, put it behind Nginx, HTTPS, and authentication before opening access.
