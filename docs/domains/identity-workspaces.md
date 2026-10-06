# Identity and workspaces

## Purpose

Identity authenticates people; workspaces define tenant ownership and authorization. A user may belong to multiple workspaces through explicit membership. UI may call a workspace a shop, but persistence and API vocabulary remain `workspace`.

## Current capability

- FastAPI-owned registration, login, logout and rotating refresh sessions.
- Email verification/password recovery when a real delivery adapter is configured.
- Workspace creation and owner membership in one transaction.
- Roles `owner`, `admin` and `member`, checked server-side.
- Workspace-scoped dashboard routes and negative tenant tests.

## Complete domain capability

- Invitations, membership lifecycle and ownership transfer.
- Capability-aware roles for channel connections, inbox assignment, contacts, analytics and billing.
- Workspace settings, timezone, privacy policy and data lifecycle controls.
- Auditable privileged changes without recording credentials or customer content.

## Invariants

- Registration creates a user/session, not an implicit workspace.
- Email uniqueness uses a documented normalization policy; errors do not enumerate accounts.
- Passwords and refresh/reset tokens are stored only as secure hashes.
- Current membership is loaded for sensitive actions; a stale token role is not authoritative.
- Slugs, UUIDs and frontend-hidden controls do not grant authorization.
- Cross-workspace resources return a non-leaking denial appropriate to the route.

See [`../reference/data-model.md`](../reference/data-model.md), [`../reference/api.md`](../reference/api.md) and [`../security.md`](../security.md).
