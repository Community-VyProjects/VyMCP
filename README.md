# VyMCP

[![CI](https://github.com/Community-VyProjects/VyMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/Community-VyProjects/VyMCP/actions/workflows/ci.yml)

> MCP server for VyOS routers, powered by [VyManager](https://github.com/Community-VyProjects/VyManager).

VyMCP lets AI agents read and manage VyOS routers through the VyManager API — inheriting VyManager's authentication, RBAC, audit, and commit-confirm safety. It never talks to routers directly.

> **Status: alpha.** Runs local (stdio) or as a shared hosted server (http); interfaces may change.

## Install

```bash
pipx install git+https://github.com/Community-VyProjects/VyMCP   # provides `vymcp`
```

Or `pip install .` from a clone, or run the Docker image `ghcr.io/community-vyprojects/vymcp` (attached, with `-i`).

## Configure

Set environment variables (see `.env.example`):

| Variable | Required | Purpose |
|---|---|---|
| `VYMANAGER_BASE_URL` | yes | VyManager API URL |
| `VYMANAGER_API_TOKEN` | yes | A `vym_` token (Sites → API Tokens; read-only recommended) |
| `VYMANAGER_ENABLE_WRITES` | no | Enable write tools (default off) |

`VYMANAGER_VERIFY_SSL` (default `true`) and `VYMANAGER_TIMEOUT` (default `30`) are optional.

## Connect an MCP client

```json
{
  "mcpServers": {
    "vymcp": {
      "command": "vymcp",
      "env": {
        "VYMANAGER_BASE_URL": "https://vymanager.example.com",
        "VYMANAGER_API_TOKEN": "vym_…"
      }
    }
  }
}
```

## Hosted deployment (shared server)

Run one VyMCP that many engineers connect to over HTTP, each authenticating with
their own VyManager token per request:

```bash
docker compose up -d          # see docker-compose.yml
```

Set `VYMANAGER_BASE_URL` and `VYMCP_PUBLIC_URL` in the compose file. Engineers point
their MCP client at `https://<vymcp>/mcp` with `Authorization: Bearer vym_…`.
Terminate TLS at a reverse proxy and run a single replica (the pending-change store
is in-memory).

## Tools

- **Read** (always): `list_instances`, `list_features`, `get_capabilities`, `get_config`.
- **Write** (only when `VYMANAGER_ENABLE_WRITES=true`): `describe_feature_operations` + `propose_operations` cover ~86 features; `apply_change` / `confirm_change` / `discard_changes` / `get_pending_changes` drive the rollout.

Writes are safe by design: off by default, capped to the token's scope, and gated by a **propose → apply** flow. `apply_change` requires explicit confirmation and rides VyManager's commit-confirm auto-rollback (a lockout safety net) — it never auto-confirms.

## Development

```bash
pip install -e ".[dev]"
pytest && ruff check . && mypy
```

## License

GPLv3 — see [`LICENSE`](LICENSE).
