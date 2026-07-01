# VyMCP — repository guidance for reviewers and Copilot

VyMCP is a **thin** Model Context Protocol server that wraps the
[VyManager](https://github.com/Community-VyProjects/VyManager) REST API so AI
agents can read and manage VyOS routers. It never talks to VyOS directly.

When reviewing changes, check these project invariants:

## Architecture
- **Everything goes through VyManager.** All calls use `VyManagerClient`
  (`src/vymcp/client.py`) against the VyManager API. No direct VyOS/device access,
  and no SSH/HTTP to routers.
- **Writes use exactly one endpoint per feature:** `POST /vyos/<feature>/batch`.
  There are no per-entity write endpoints.
- **Do not reimplement VyOS grammar in VyMCP.** Validation stays *structural*
  (non-empty, whitespace, counts, op-name-in-vocabulary). Semantic validity is
  VyManager's and VyOS's job — surface their errors, don't pre-judge them. (A past
  bug came from VyMCP encoding a VyOS rule and getting it wrong.)

## Write guardrails (must not weaken)
- Write tools are registered **only** when `VYMANAGER_ENABLE_WRITES=true`, on top
  of the token's own read-only scope (VyManager rejects a read-only token anyway).
- Writes follow **propose → apply**: a `propose_*` tool builds a plan and touches
  nothing; `apply_change(plan_id, confirm=true)` executes one reviewed plan. Plans
  are single-use, TTL-bound, and instance-bound (`src/vymcp/changes.py`).
- **commit-confirm is a lockout safety net, not an undo.** Never auto-confirm.
  To undo a change that didn't lock you out: confirm, then apply the inverse.
  `discard_changes` must refuse while a commit-confirm is pending.

## Quality gate
- `ruff check .`, `mypy`, and `pytest` must all pass (see `.github/workflows/ci.yml`).
- Tests are deterministic — no live device or network (httpx `MockTransport`). New
  tools should come with tests.
- No secrets in code or logs; the API token comes from the environment.
