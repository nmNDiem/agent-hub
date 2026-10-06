# Authentication, authorization and multi-tenancy

## Authentication is owned by the backend
No Supabase Auth assumption. Backend stores normalized email and Argon2id password hashes; enforce minimum password rules, rate limit by IP + email hash, generic invalid-credential response and server-side audit. Email verification/password recovery must be backed by actual configured delivery provider before exposed; recovery tokens random, hashed and short-lived.

## Cookie session flow
Login creates short-lived signed access token (suggest 10–15 min) and random rotating refresh session (suggest ~7–30 days depending deployment policy). Cookies `HttpOnly; Secure` in HTTPS production; same-origin via reverse proxy (`/api/v1` → FastAPI). Set `SameSite=Lax` unless deployment requires another well-justified mode; scope refresh cookie narrowly. Avoid localStorage/sessionStorage bearer tokens. Refresh endpoint rotates and invalidates previous refresh token, stores **hash** in DB and revokes family on reuse; logout revokes session. Access token has `sub` UUIDv7, `iss`, `aud`, `iat`, `exp`, `jti`; verify signature/algorithm/audience and current user status. Current workspace membership is checked by DB on sensitive actions, not embedded role trusted forever from a token.

## CSRF and proxy
State-changing cookie-auth API must validate Origin/Referer as applicable and use a CSRF token or robust double-submit token for unsafe methods; CORS is not CSRF protection. Next.js same-origin path `/api/v1/*` reverse proxies FastAPI; Next server components forwarding cookies must not cache personal responses publicly. FastAPI is auth authority; do not invent two independent sessions in Next and FastAPI.

## Authorization algorithm
Resolve agent/conversation/document by public ID or internal ID; query with `workspace_id` or join; verify `workspace_members(user_id, workspace_id)` and capability; check that the entity belongs to the workspace; return 404 for unauthorized resource discovery where appropriate; log safe denial. Every list uses `WHERE workspace_id = :authorized_workspace_id`, not a broad list later filtered in JavaScript. Background jobs, Storage object keys, embeddings and cache keys carry workspace/agent scope. Recheck after switching workspace. Resource public IDs are identifiers, not proof of authorization.

## RLS and service keys
Because custom JWTs are **not** Supabase Auth JWTs, do not copy example `auth.uid()` RLS policies and assume they protect this app. Architecture invariant: **all DB/Storage privileged traffic stays server-side**. The FastAPI app enforces tenancy and uses a restricted database role; PostgreSQL RLS may add defense-in-depth using transaction-local `app.workspace_id` and `FORCE ROW LEVEL SECURITY` where carefully designed and tested. Service role keys can bypass Storage RLS: keep them server-only, and have the backend authorize each Storage operation first. Never expose a service role key to the browser. See official Supabase security docs referenced in `security-operations.md`.

## Anonymous public widget
Public bot UUIDv7 + domain allowlist + published state + rate limit/quota + short-lived anonymous bot/session token. Origin validation is defense-in-depth, **not authentication** (non-browser clients can forge Origin). Anonymous token cannot call admin routes, list files or switch bot. A guessed bot public ID must not expose draft config, documents, API keys or other tenants.
