# VyMCP

[![CI](https://github.com/Community-VyProjects/VyMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/Community-VyProjects/VyMCP/actions/workflows/ci.yml)

> Model Context Protocol (MCP) server for VyOS routers, powered by [VyManager](https://github.com/Community-VyProjects/VyManager).

VyMCP lets AI agents and MCP-aware tools (Claude, IDEs, automation) **read and manage VyOS routers** through a safe, audited interface. Rather than talking to routers directly, VyMCP wraps the VyManager API — so every action inherits VyManager's per-user authentication, role-based access control, audit logging, and version-aware (VyOS 1.4 / 1.5) configuration handling.

> **Status: alpha.** Read tools cover every VyManager feature; guarded write tools cover ~86 features through a generic, discovery-driven proposer (plus curated firewall-group tools). The transport is stdio today (hosted HTTP/SSE is planned). Interfaces may still change.

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
| `describe_feature_operations(feature)` | The operations available for a feature (op names, arg counts, descriptions, and any required top-level/subject fields). |
| `propose_operations(feature, instance_id, operations, fields)` | Generic proposer — build a change for **~86 features** from the discovered vocabulary (no effect until applied). |
| `propose_create_address_group` / `propose_add_address_group_members` / `propose_remove_address_group_members` / `propose_delete_address_group` | Curated firewall address-group proposers (nicer ergonomics for a common case). |
| `apply_change(plan_id, confirm)` | Apply a proposed plan, protected by VyManager's commit-confirm when available. |
| `confirm_change(instance_id)` | Keep a pending commit-confirm change (settles the device, stops the rollback). |
| `discard_changes(instance_id)` | Drop unsaved changes — only when no commit-confirm is pending. |
| `get_pending_changes(instance_id)` | Show the commit-confirm rollback window and any pending change. |

`propose_operations` covers every feature whose batch handler dispatches uniformly — the routing, firewall, NAT, service, VPN, system surface plus interface sub-types. A few features with bespoke handlers (`route`, bridge firewall, `ethernet`) are intentionally **not** exposed generically, because their custom per-op wiring can't be driven safely by introspection alone; manage those in the VyManager UI.

### Guardrails

- **Read-only by default** — write tools are not even registered unless `VYMANAGER_ENABLE_WRITES=true`, on top of the token's own read-only scope (a read-only token is rejected by VyManager regardless).
- **Vocabulary-bound, not arbitrary** — `propose_operations` only accepts operations that exist in the feature's discovered vocabulary (validated against VyManager's own contract); there is no "set any path" tool.
- **Propose → apply** — `apply_change` requires `confirm=true` and a valid plan id, so the model can only apply a change a human has seen.
- **Never auto-confirms** — applied changes ride VyManager's commit-confirm timer. That timer is a *lockout safety net*: if a change cuts off access to the router, the device auto-reverts (reboots) and you regain access. To keep a change, call `confirm_change`; to undo one that didn't lock you out, `confirm_change` then apply the inverse change.

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
- [x] Generic, discovery-driven writes across ~86 features
- [ ] Cover the remaining bespoke-handler features (`route`, bridge firewall, `ethernet`)
- [ ] Hosted remote transport (HTTP/SSE) with per-user auth
- [ ] Packaging and deployment docs

## Related projects

- **[VyManager](https://github.com/Community-VyProjects/VyManager)** — the web UI and API that VyMCP builds on.

## License

See `LICENSE` for details.
