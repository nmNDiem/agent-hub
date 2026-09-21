# Security, observability, reliability, costs

## Mandatory threat review
- Credential stuffing/account enumeration -> Argon2id, dummy verify, IP/account throttles, generic errors, recovery token limits.
- CSRF/session fixation -> CSRF control, Origin check, refresh rotation/reuse detection, secure cookies.
- Tenant bleed -> scoped DB/retrieval/cache/storage/job keys and cross-shop tests; UUID is not an access-control system.
- Prompt injection in knowledge/images -> treat content as data, constrained tool calls, server output validation, per-shop retrieval.
- Uploaded file exploits -> magic bytes, caps, image decode checks, private storage, limited parser runtime.
- SSRF -> no arbitrary media URL proxying or server-side fetching from chatbot user strings.
- XSS -> sanitized chat markdown, safe product URLs, widget iframe/CSP, reject dangerous schemes.
- Budget exhaustion -> input/output token caps, image caps, bot/shop/IP/session quotas, timeout/concurrency limits.
- Secrets -> service role/DB/OpenAI credentials only on backend; redact logs and traces; no .env committed.

## Telemetry
Generate request_id at edge; trace safe span IDs across API/LLM/ingestion; use counts, latency distributions (P50/P95), first-token latency, provider failures, queue age, retrieval empty rate, token/cost meters and widget conversion events *only if implemented and disclosed*. Never log passwords, access/refresh tokens, raw customer photos or full conversations by default. Admin audit: login failure classes, publish, bot config edits, knowledge deletion, member actions, secret rotation.

## Availability
Use health endpoints `/health/live` and `/health/ready` (readiness checks DB, not live OpenAI if too expensive). Circuit-breaker/backoff for provider outage and rate limits; SSE heartbeat and client abort detection; index job retries with max attempts and dead-letter status. Backups, restore drill and retention policy before production. Structured errors with request ID and safe user text.

## Security references verified 2026-09-21
- PostgreSQL UUID data type/generation: https://www.postgresql.org/docs/18/datatype-uuid.html and https://www.postgresql.org/docs/18/functions-uuid.html
- Python `uuid.uuid7` Python 3.14+: https://docs.python.org/3.14/library/uuid.html
- FastAPI JWT/Argon2 example: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- Supabase Storage access policy/service key caveat: https://supabase.com/docs/guides/storage/security/access-control
- Supabase private/signed URL semantics: https://supabase.com/docs/guides/storage/buckets/fundamentals

Verify actual deployed library/provider behavior and project PG version before enabling production features.
