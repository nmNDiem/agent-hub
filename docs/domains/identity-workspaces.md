# Identity and workspaces

## Function and ownership

Identity authenticates people. A Workspace is the generic tenant and authorization boundary; it is not inherently a shop. Membership joins users to workspaces with `owner`, `admin`, or `member` roles.

## CURRENT

- FastAPI-owned registration, login, logout, email verification/recovery adapters, and rotating refresh sessions.
- Workspace creation plus owner membership in one transaction.
- Server-side membership checks on workspace routes and negative cross-tenant tests.
- A user may belong to multiple workspaces; registration does not create one implicitly.

Main data: users, auth/email tokens, workspaces, and workspace members. Main surfaces: authentication and workspace settings/switching.

## Core flow

Authenticate user → resolve workspace from the route → load current membership → authorize the operation → scope every repository query to that workspace. Client IDs, slugs, hidden controls, and token-embedded stale roles are never sufficient.

## Invariants

- Normalize email consistently and avoid account enumeration.
- Store passwords and session/reset tokens only as secure hashes.
- Return a non-leaking denial for cross-workspace resources.
- Switching workspace cancels requests and clears tenant-scoped UI cache/drafts.

## APPROVED DIRECTION

Invitations, membership lifecycle, ownership transfer, capability-aware permissions, workspace policy settings, and content-minimized audit of privileged changes.

## NOT IMPLEMENTED

No generic per-resource ACL engine, enterprise identity federation, or platform-support impersonation model exists.

## Change trigger

Add finer permissions only when a shipped workflow cannot be safely expressed by the three current roles; define the resource/action matrix before changing persistence.

Related authority: [`../security.md`](../security.md), [`../data-model.md`](../data-model.md), [`../api.md`](../api.md).
