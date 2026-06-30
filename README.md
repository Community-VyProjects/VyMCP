# VyMCP

> Model Context Protocol (MCP) server for VyOS routers, powered by [VyManager](https://github.com/Community-VyProjects/VyManager).

VyMCP lets AI agents and MCP-aware tools (Claude, IDEs, automation) **read and manage VyOS routers** through a safe, audited interface. Rather than talking to routers directly, VyMCP wraps the VyManager API — so every action inherits VyManager's per-user authentication, role-based access control, audit logging, and version-aware (VyOS 1.4 / 1.5) configuration handling.

> **Status: early development.** The VyManager-side foundation (per-user API tokens, instance scoping, read-only scopes, audit attribution) is in place. The MCP server itself is being built against that contract. Interfaces will change.

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

## Capabilities (planned)

VyMCP follows a **read-first** rollout:

- **Read (all features):** `list_features`, `get_capabilities`, `get_config` — surface VyOS configuration and status across every VyManager feature.
- **Curated writes (later):** typed, high-value tools (firewall rules, interfaces, NAT, static routes, …) with a preview-then-apply step wired to VyManager's commit-confirm flow.

## Requirements

- A reachable [VyManager](https://github.com/Community-VyProjects/VyManager) instance.
- A VyManager API token (read-only recommended to start).
- One or more VyOS 1.4 / 1.5 routers registered in VyManager.

## Getting started

Setup instructions will land here as the server takes shape. At a high level, VyMCP will be configured with:

- the base URL of your VyManager API,
- a `vym_` API token for authentication.

## Roadmap

- [ ] MCP server skeleton (stdio transport) + token auth to VyManager
- [ ] Generic read tools across all features
- [ ] Hosted remote transport (HTTP/SSE) with per-user auth
- [ ] Curated write tools with preview / commit-confirm
- [ ] Packaging and deployment docs

## Related projects

- **[VyManager](https://github.com/Community-VyProjects/VyManager)** — the web UI and API that VyMCP builds on.

## License

See `LICENSE` for details.
