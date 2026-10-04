# 08 — Security and privacy baseline

## Custom email/password auth (confirmed approach)
- FastAPI owns the credential and session lifecycle; **do not** use Supabase Auth or assume app JWTs authenticate to Supabase PostgREST/Storage automatically.
- Hash passwords with a modern adaptive KDF (Argon2id proposed via `pwdlib[argon2]`); never plaintext, reversible encryption or logs.
- Normalize email carefully; generic error responses to avoid account enumeration; brute-force/rate limits; email verification and expiring single-use password reset.
- Short access lifetime (15 minutes proposed), rotating refresh sessions with hashes in database; revoke on logout/password reset and detect refresh replay; secrets from secret manager/environment.
- For browser app, propose short access token in memory and refresh in Secure/HttpOnly/SameSite cookie; assess cross-site deployments and CSRF explicitly. Never put bearer tokens in public embed snippets or localStorage by default.
- Audit owner/admin actions without storing credentials or raw chat text in audit logs.
- Consented lead PII is never written to routine logs or public responses. Owner/admin access is checked server-side; CSV cells beginning with spreadsheet formula markers are neutralized.

## Authorization and tenant separation
- For owner API: authenticate -> membership lookup -> check role -> read/write workspace-scoped row. Never trust `workspace_id` just because supplied in URL/body.
- For visitor API: active immutable published revision + exact allowed origin + short-lived opaque visitor session -> derive workspace/agent from server DB and verify every conversation, image and product-image grant belongs to that session.
- Lead capture additionally requires the matching open conversation, explicit current-version consent, a validated email or phone and session-scoped idempotency; client-supplied tenant/agent identity is not accepted.
- All SQL and background tasks filter workspace. Every Qdrant request injects the validated workspace/allowed-source filter server-side, and returned chunk IDs are revalidated against active Postgres rows before use. Qdrant is never reachable from browser/widget code.
- With custom auth and direct server-side SQL, Supabase `auth.uid()` is not automatically the FastAPI user ID. Do not write RLS policies assuming otherwise. If applying transaction-local tenant context, set it only after validated auth and use a DB role without RLS-bypass privileges.
- Do not expose `service_role`, Supabase secret API keys or Qdrant credentials. Server-side privileged Storage/Qdrant access requires *app-side checks* before every action; elevated credentials bypass client-facing controls.

## Storage and uploads
- Store private knowledge docs and visitor photos in private buckets; server authorizes any signed URL and uses short expiry. Public product images only if shop elects to publish them.
- Enforce allowlist MIME + file signature and decoded format, bounded upload bytes/pixels/pages, safe filenames, path constraints, per-workspace quotas and scan/isolated parsing as needed.
- Treat PDF parsing as hostile execution: use strict parsing in a subprocess with wall/CPU/memory/output limits and fail closed if resource isolation cannot be installed. Application page/text limits do not replace decoder-level isolation.
- Never use uploaded document or image metadata as executable code; no unrestricted URL fetching. Prefer blocking SSRF via allowlisting if crawling added later.
- Visitor sessions/transcripts carry bounded expiry/retention timestamps (24 hours by default); uploaded images have per-file/pixel/session quotas, single-use attachment handles and explicit conversation deletion. An operational sweeper, backup deletion policy and jurisdiction-specific privacy review remain mandatory before production under F5/P7.

## LLM and abuse
- Separate system/tool policy from untrusted user messages/documents; retrieved text is data, not commands.
- Fixed tool allowlist, validated arguments, least privilege, cost/token caps per request/workspace, provider timeouts and concurrency limits.
- No payment/checkout/order mutation from an LLM. No speculation about stock, private order status or unsupported size guarantees.
- Redact API keys, passwords, tokens, contact info and private file links from error logs/traces where practical.
- Knowledge workers log job/workspace identifiers and stable error codes only; never log uploaded bytes, extracted/chunk text or parser tracebacks. Ingestion merely preserves text as untrusted data—prompt-injection defenses are enforced later when grounded context is assembled and tools execute.

## Test requirements
- Login/token rotation/password reset tests; wrong user/workspace access to each resource; mandatory Qdrant tenant/source filters plus Postgres result revalidation; unauthorized signed-URL attempt; malformed image and oversized PDF; widget replay, rate limits and consent; prompt injection from uploaded docs; safe error behavior.

## Authoritative implementation reading
- FastAPI JWT and password hashing: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- Supabase RLS / service privilege: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase private buckets: https://supabase.com/docs/guides/storage/buckets/fundamentals
- Supabase Storage authorization: https://supabase.com/docs/guides/storage/security/access-control
