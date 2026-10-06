# 17 — Local now, Docker on VPS later

## Confirmed plan
**NOW:** developer laptop runs Next.js dashboard and FastAPI against isolated Supabase Postgres/Storage and Qdrant development resources, with an OpenAI dev API key. **LATER:** containerize application services and run them on VPS; Supabase Postgres/Storage remain external managed services, while Qdrant placement is selected during deployment planning. No current VPS, domain, public HTTPS endpoint or production environment is assumed.

## Local setup contract
- Document prerequisites and actual verified start commands in README after scaffold; no fictional scripts.
- Provide `.env.example` for deployment-specific endpoints, resource namespaces, model/profile selections and server-side secrets with placeholder values only. Keep stable application policy, limits and internal version defaults in typed config instead of duplicating them in `.env.example`.
- Keep `.env*` with secrets out of version control; fail startup clearly for missing required settings.
- Use migrations against a **development** DB only; seed fake shop/catalog data, never real customer records.
- Make frontend/backend/widget local CORS, cookie, SSE and upload paths explicit; document whichever Supabase local/hosted-dev strategy actually works.
- Unit tests use fake embedding/vector adapters without Docker. F3 integration tests require an explicitly configured non-production Qdrant server; local development must not silently fall back to different in-process search semantics.

## VPS release design (future approved phase)
1. Select VPS sizing/vendor; document OS patching, firewall, non-root service accounts and SSH key policy.
2. Build pinned/scanable Next.js + FastAPI images, and worker only if jobs require it; run containers as non-root.
3. Reverse proxy TLS, health/readiness, secure cookie/origin config, secret injection and egress allowlists.
4. External Supabase connectivity, Qdrant placement/persistence, migrations/re-index rollback, object permissions and backups; validate restore or deterministic vector rebuild, not just backup existence.
5. Centralized redacted logs, metrics, alerting, cost/usage caps and incident playbook.
6. CI builds/tests; staging smoke test; approve production rollout; rollback plan for incompatible schema/client/widget releases.
7. Document disaster recovery targets, retention and emergency key/session revocation.

## Security/operations hazards
FastAPI custom JWTs do not authorize client calls to Supabase or Qdrant. Do not place service-role or Qdrant/OpenAI keys in Next.js client variables or widget assets. A VPS snapshot does not by itself back up external Supabase or Qdrant. Back up authoritative DB/Storage appropriately and verify that Qdrant can be restored or rebuilt. Avoid multiple uncoordinated workers for non-idempotent ingestion or channel delivery.

## Exit conditions
Foundation acceptance requires local boot and tests. Production needs separate rollout authorization, approved domain/TLS/config, migration verification, performance budgets, monitoring, data retention and completed security review. Never label MVP docs as an already deployed product.

## Local-pilot operations
F5.3 provides database-backed liveness/readiness, redacted route-template request logs and a bounded one-shot retention command. Apply migrations before running it. Local scheduling remains an operator responsibility; Docker, a VPS scheduler and centralized monitoring belong to P7. See the archived [`local-pilot-runbook.md`](../operations/local-pilot-runbook.md) for the historical commands and checklist.
