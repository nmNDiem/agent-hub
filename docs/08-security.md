# 08 — Security and privacy baseline

## Custom email/password auth (confirmed approach)
- FastAPI owns the credential and session lifecycle; **do not** use Supabase Auth or assume app JWTs authenticate to Supabase PostgREST/Storage automatically.
- Hash passwords with a modern adaptive KDF (Argon2id proposed via `pwdlib[argon2]`); never plaintext, reversible encryption or logs.
- Normalize email carefully; generic error responses to avoid account enumeration; brute-force/rate limits; email verification and expiring single-use password reset.
- Short access lifetime (15 minutes proposed), rotating refresh sessions with hashes in database; revoke on logout/password reset and detect refresh replay; secrets from secret manager/environment.
- For browser app, propose short access token in memory and refresh in Secure/HttpOnly/SameSite cookie; assess cross-site deployments and CSRF explicitly. Never put bearer tokens in public embed snippets or localStorage by default.
- Audit owner/admin actions without storing credentials or raw chat text in audit logs.

## Authorization and tenant separation
- For owner API: authenticate -> membership lookup -> check role -> read/write workspace-scoped row. Never trust `workspace_id` just because supplied in URL/body.
- For visitor API: published `agent_id` + short-lived scoped visitor session -> derive workspace/agent from server DB, verify conversation belongs to that session.
- All SQL (including semantic vector and background tasks) filters workspace. Use constrained Postgres roles and RLS where feasible as defense in depth; beware elevated roles bypass RLS.
- With custom auth and direct server-side SQL, Supabase `auth.uid()` is not automatically the FastAPI user ID. Do not write RLS policies assuming otherwise. If applying transaction-local tenant context, set it only after validated auth and use a DB role without RLS-bypass privileges.
- Do not expose `service_role` or Supabase secret API keys. Server-side privileged Storage access requires *app-side checks* before every action; elevated key bypasses RLS.

## Storage and uploads
- Store private knowledge docs and visitor photos in private buckets; server authorizes any signed URL and uses short expiry. Public product images only if shop elects to publish them.
- Enforce allowlist MIME + file signature and decoded format, bounded upload bytes/pixels/pages, safe filenames, path constraints, per-workspace quotas and scan/isolated parsing as needed.
- Never use uploaded document or image metadata as executable code; no unrestricted URL fetching. Prefer blocking SSRF via allowlisting if crawling added later.
- Document retention and deletion for visitor images/chat/PII prior to production; default to minimum necessary retention and protect backups appropriately.

## LLM and abuse
- Separate system/tool policy from untrusted user messages/documents; retrieved text is data, not commands.
- Fixed tool allowlist, validated arguments, least privilege, cost/token caps per request/workspace, provider timeouts and concurrency limits.
- No payment/checkout/order mutation from an LLM. No speculation about stock, private order status or unsupported size guarantees.
- Redact API keys, passwords, tokens, contact info and private file links from error logs/traces where practical.

## Test requirements
- Login/token rotation/password reset tests; wrong user/workspace access to each resource; tenant filter in tool/vector retrieval; unauthorized signed-URL attempt; malformed image and oversized PDF; widget replay, rate limits and consent; prompt injection from uploaded docs; safe error behavior.

## Authoritative implementation reading
- FastAPI JWT and password hashing: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- Supabase RLS / service privilege: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase private buckets: https://supabase.com/docs/guides/storage/buckets/fundamentals
- Supabase Storage authorization: https://supabase.com/docs/guides/storage/security/access-control
