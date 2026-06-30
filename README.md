# VyMCP

> Model Context Protocol (MCP) server for VyOS routers, powered by [VyManager](https://github.com/Community-VyProjects/VyManager).

VyMCP lets AI agents and MCP-aware tools (Claude, IDEs, automation) **read and manage VyOS routers** through a safe, audited interface. Rather than talking to routers directly, VyMCP wraps the VyManager API — so every action inherits VyManager's per-user authentication, role-based access control, audit logging, and version-aware (VyOS 1.4 / 1.5) configuration handling.

> **Status: alpha.** Read tools cover every VyManager feature; guarded write tools currently cover firewall address groups, with more features being added. The transport is stdio today (hosted HTTP/SSE is planned). Interfaces may still change.

---

## Why a server, not a direct integration

VyMCP deliberately **does not** connect to VyOS devices itself. It is a thin, stateless translation layer in front of VyManager's REST API. This keeps a single, enforced source of truth for everything that matters in an enterprise environment:

- **Per-user identity** — a VyMCP request acts as a real VyManager user, never a shared service account.
- **RBAC** — a token can never exceed its owner's permissions.
- **Audit** — every configuration change is attributed to the user, token, and instance.
- **Commit-confirm safety** — writes ride VyManager's existing safety rails.
- **Version awareness** — VyOS 1.4 vs 1.5 differences are handled by VyManager, not reimplemented here.

```
  MCP client (Claude / IDE / agent)
        │   MCP over HTTP+SSE (or stdio)
        ▼
     VyMCP  ── stateless translation layer
        │   Authorization: Bearer vym_…
        │   X-VyOS-Instance-Id: <instance>
        ▼
   VyManager API ── RBAC · audit · commit-confirm · 1.4/1.5 mappers
        │
        ▼
    VyOS 1.4 / 1.5
```

## Security model

VyMCP authenticates to VyManager with a **personal access token** that a user mints in the VyManager UI (Sites → API Tokens). Tokens are least-privilege by design:

- **Read-only scope** — a token can be restricted so it can never make configuration changes.
- **Instance/site scoping** — a token can be limited to specific routers or sites (always within the user's own grants).
- **Per-call targeting** — the target router is selected per request via the instance the token is allowed to reach.

This means you can hand VyMCP a token that, for example, can only *read* a single production router — and that limit is enforced by VyManager, not by VyMCP.

## Tools

**Read (always available):**

| Tool | Purpose |
|---|---|
| `list_instances` | The instances this token can reach (returns `instance_id`s for the other tools). |
| `list_features` | Every VyOS feature VyMCP can read. |
| `get_capabilities(feature, instance_id)` | Version-aware capability flags for a feature. |
| `get_config(feature, instance_id)` | Normalized configuration for a feature. |

**Write (only when `VYMANAGER_ENABLE_WRITES=true`):** changes go through a mandatory
**propose → apply** flow — a `propose_*` tool validates and returns a `plan_id` without
touching anything, then `apply_change(plan_id, confirm=true)` executes that one reviewed
plan. Plans are single-use, time-limited, and bound to their target instance.

| Tool | Purpose |
|---|---|
| `propose_create_address_group` / `propose_add_address_group_members` / `propose_remove_address_group_members` / `propose_delete_address_group` | Build a firewall address-group change (no effect until applied). |
| `apply_change(plan_id, confirm)` | Apply a proposed plan, using VyManager's commit-confirm auto-rollback when available. |
| `confirm_change(instance_id)` | Make a pending commit-confirm change permanent. |
| `discard_changes(instance_id)` | Revert unsaved changes on an instance. |
| `get_pending_changes(instance_id)` | Show the commit-confirm rollback window and any pending change. |

### Guardrails

- **Read-only by default** — write tools are not even registered unless `VYMANAGER_ENABLE_WRITES=true`, on top of the token's own read-only scope (a read-only token is rejected by VyManager regardless).
- **No arbitrary config** — only curated, typed operations; there is no "set any path" tool.
- **Propose → apply** — `apply_change` requires `confirm=true` and a valid plan id, so the model can only apply a change a human has seen.
- **Never auto-confirms** — applied changes ride VyManager's commit-confirm timer and auto-revert unless explicitly confirmed.

## Requirements

- A reachable [VyManager](https://github.com/Community-VyProjects/VyManager) instance.
- A VyManager API token (Sites → API Tokens; read-only recommended to start).
- One or more VyOS 1.4 / 1.5 routers registered in VyManager.
- Python 3.10+.

## Getting started

Install:

```bash
pip install -e .          # or: pip install -e ".[dev]" for tests
```

Configure via environment variables (see `.env.example`):

```bash
export VYMANAGER_BASE_URL="https://vymanager.example.com"
export VYMANAGER_API_TOKEN="vym_…"      # read-only recommended
# export VYMANAGER_ENABLE_WRITES=true   # opt in to write tools
```

Register with an MCP client (stdio). Example client config:

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

## Development

```bash
pip install -e ".[dev]"
pytest          # deterministic; no live device needed
ruff check .
mypy
```

## Roadmap

- [x] stdio server + token auth to VyManager
- [x] Read tools across all features
- [x] Guarded write tools (propose → apply → commit-confirm)
- [ ] More curated write features
- [ ] Hosted remote transport (HTTP/SSE) with per-user auth
- [ ] Packaging and deployment docs

## Related projects

- **[VyManager](https://github.com/Community-VyProjects/VyManager)** — the web UI and API that VyMCP builds on.

## License

See `LICENSE` for details.
