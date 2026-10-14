# Security and privacy invariants

These rules apply to every phase and override convenience or UI assumptions.

## Identity and authorization

- FastAPI owns email/password authentication, access cookies, rotating refresh sessions, verification and recovery. Custom tokens are not Supabase Auth tokens.
- Every dashboard action authenticates the user, loads current workspace membership, checks capability and scopes the resource query. A URL/body `workspace_id` is never sufficient.
- Every public channel request resolves workspace, agent, conversation and contact identity from trusted server-side connection/session state.
- Public UUIDs and embed IDs are identifiers, not secrets or authorization grants.
- Cross-workspace reads/writes, joins, jobs, vector searches, Storage access and tool calls must be denied and covered by negative tests.

## Secrets and provider credentials

- Database credentials, Supabase service keys, OpenAI keys, Qdrant credentials, channel access tokens and JWT signing keys remain server-side and out of logs, browser bundles and commits.
- Channel credentials are encrypted at rest using an approved key-management approach and are never returned after initial submission.
- Facebook Page tokens and Zalo OAuth/verifier/OA signing secrets use Supabase Vault authenticated encryption. Application records contain
  only opaque Vault UUID references; Vault root-key preservation and least-privilege access are
  deployment requirements.
- Webhook authenticity is validated with the provider mechanism before message processing. When
  verification material is connection-specific, as with Zalo OA secrets, a bounded untrusted
  provider-account ID may select only a server-owned candidate credential; no tenant data is
  processed or disclosed until signature verification succeeds.

## Tenant-owned data

- Every tenant-owned table has `workspace_id` or a provably tenant-scoped parent relationship; repositories accept trusted tenant context.
- Qdrant searches inject workspace and allowed-source filters server-side, then revalidate returned chunks against active PostgreSQL generations.
- Private Storage access requires independent authorization before a short-lived signed URL or backend redirect is issued.
- Channel external IDs are namespaced by provider and connection; an external ID alone is never globally trusted.

## Authentication and browser safety

- Passwords use a modern adaptive hash; raw passwords and reset tokens are never stored or logged.
- Login/recovery responses avoid account enumeration; brute-force controls apply by IP and normalized account signal.
- Auth cookies are HttpOnly and appropriately Secure/SameSite; unsafe cookie-authenticated requests require CSRF protection.
- User-specific responses are private/no-store. Access tokens do not belong in localStorage or public URLs.

## Channels and messaging

- Inbound events are size-limited, authenticated, normalized and deduplicated before any paid model call.
- Retries reuse persisted message/delivery identity so duplicate webhooks cannot produce duplicate conversations or model charges.
- Provider message windows, opt-outs and permissions are enforced independently of model output.
- Media downloads use provider allowlists, bounded time/size, content verification, private quarantine and no arbitrary URL fetching.
- A human or AI sender is explicit; the system never impersonates a staffed live service.

## AI and tools

- User messages, documents, websites, image metadata and provider payloads are untrusted data and cannot override system/tool policy.
- Tools use allowlisted typed inputs, server-injected tenant scope, independent authorization, bounded results and audited safe metadata.
- Current catalog records own price, SKU, options and inventory. The model cannot invent availability, discount, shipping guarantees or order outcomes.
- Token, tool-call, provider-call, concurrency and workspace quotas are enforced before external spend where possible.
- No autonomous payment, order, refund or stock mutation is authorized.

## Uploads and retention

- Validate MIME, signature, decoded format, byte/pixel/page limits and server-generated object paths. Parse hostile documents in an isolated bounded process.
- Knowledge documents and visitor images stay private; public product media requires deliberate publication.
- Local defaults are 24-hour visitor sessions/transcripts, 30-minute unattached images, one-hour attached images and 30-day consented leads. A change requires an explicit retention decision.
- Expiry revokes authoritative database access before best-effort external cleanup; failed Storage deletion remains retryable.

## Logging and errors

- Routine logs contain request/correlation ID, method, route template, status, duration and safe identifiers only.
- Never log request bodies, raw query strings, authorization/cookie values, chat text, images, document chunks, email, phone, prompts, provider tokens or private object keys.
- Client errors use stable codes and safe messages with a request ID; no traceback, internal prompt or provider response leakage.

## Required security tests

Every newly exposed tenant resource requires a negative cross-workspace test. Channel work additionally requires invalid signature/challenge, wrong connection, duplicate/reordered event, revoked token, media limit and outbound retry tests. See [`testing.md`](testing.md).
