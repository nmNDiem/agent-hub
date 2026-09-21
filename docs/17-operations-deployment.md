# 17 — Local now, Docker on VPS later

## Confirmed plan
**NOW:** developer laptop runs Next.js dashboard and FastAPI; use isolated Supabase Postgres/Storage development resources and OpenAI dev API key. **LATER:** containerize application services and run them on VPS; Supabase Postgres/Storage remain external managed services. No current VPS, domain, public HTTPS endpoint or production environment is assumed.

## Local setup contract for F0
- Document prerequisites and actual verified start commands in README after scaffold; no fictional scripts.
- Provide `.env.example` for `DATABASE_URL`, server-side Supabase URL/key, OpenAI API key and model IDs, token signing key and app/widget URLs with placeholder values only.
- Keep `.env*` with secrets out of version control; fail startup clearly for missing required settings.
- Use migrations against a **development** DB only; seed fake shop/catalog data, never real customer records.
- Make frontend/backend/widget local CORS, cookie, SSE and upload paths explicit; document whichever Supabase local/hosted-dev strategy actually works.
- Run local tests without requiring Docker/VPS; Docker is optional during F0.

## VPS release design (future approved phase)
1. Select VPS sizing/vendor; document OS patching, firewall, non-root service accounts and SSH key policy.
2. Build pinned/scanable Next.js + FastAPI images, and worker only if jobs require it; run containers as non-root.
3. Reverse proxy TLS, health/readiness, secure cookie/origin config, secret injection and egress allowlists.
4. External Supabase connectivity, migrations/rollback, object permissions and backups; validate restore, not just backup existence.
5. Centralized redacted logs, metrics, alerting, cost/usage caps and incident playbook.
6. CI builds/tests; staging smoke test; approve production rollout; rollback plan for incompatible schema/client/widget releases.
7. Document disaster recovery targets, retention and emergency key/session revocation.

## Security/operations hazards
FastAPI custom JWTs do not authorize client calls to Supabase. Do not place service-role keys in Next.js client variables or widget assets. A VPS snapshot does not by itself back up external Supabase. Back up DB/Storage appropriately and verify restoration. Avoid multiple uncoordinated workers for non-idempotent ingestion or channel delivery.

## Exit conditions
F0 passes with local boot and tests. Production needs separate P7 authorization, approved domain/TLS/config, migration verification, performance budgets, monitoring, data retention and completed security review. Never label MVP docs as an already deployed product.
