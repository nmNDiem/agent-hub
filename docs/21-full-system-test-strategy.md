# 21 — Full-system quality and test strategy

## Test pyramid
- Unit: auth/session token rotation, policy parser, catalog filters, size/price formatting, prompts/tools, quota and billing math.
- Integration: Postgres constraints/migrations; tenant-context queries; Supabase Storage authorization; OpenAI adapter mocked or controlled; ingestion idempotency; webhook signature/deduplication.
- End-to-end: Next.js signup -> workspace -> catalog/knowledge -> publish widget -> shopper text/photo -> grounded cards -> lead/history; run locally first.
- Operational (later): Docker image smoke tests, VPS TLS/proxy, backup restore, rollout/rollback, load/cost and channel failure recovery.

## Mandatory adversarial cases
Two workspaces with similarly named products cannot see or retrieve each other's rows/embeddings/images/conversations; wrong/expired widget session fails; unsigned Storage URL cannot be forged; public embed key cannot elevate to owner. Prompt injection in documents/images cannot make tool spend/access exceed policy. Fake stock/price prompts cannot override catalog. Authentication: enumeration, brute force throttling, refresh rotation/reuse and CSRF on cookie actions.

## Resilience cases
OpenAI timeout/rate limit/cost ceiling; SSE disconnect/retry; duplicate CSV rows; interrupted ingestion; invalid images/MIME; revoked channel token; duplicate/reordered webhook; billing event replay; database migration rollback; failed Storage deletion. Test exact server behavior and observable user messaging, not only status codes.

## Acceptance policy
Each phase in `docs/22-phase-gates.md` has a demo and reproducible test commands. Codex must report run/skip/failure honestly and add isolation tests for all new tenant-owned resources. A local pilot passing does **not** establish full production security/performance or legal compliance.
