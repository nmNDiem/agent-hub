# Local development → Docker/VPS

## Recommended local layout (two repos are optional)
```text
workspace/
  agent-hub-web/          # Next.js 3000
  agent-hub-api/          # FastAPI 8000 + Alembic + tests
  agent-hub-spec/         # this package, or canonical docs in one repo
```
Use Python 3.14+ if choosing stdlib uuid7; otherwise explicitly pin a suitable UUIDv7 package and test it. Exact Node/Next.js versions are lockfile-controlled at implementation; no blind dependency `latest`. Supabase project Postgres and Storage may be remote during local dev; never put service key in web env.

## Example env contract (placeholders, not usable values)
```dotenv
# FastAPI, server-only
APP_ENV=local
DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/DB
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=REPLACE_ME_SERVER_ONLY
OPENAI_API_KEY=REPLACE_ME_SERVER_ONLY
QDRANT_URL=http://127.0.0.1:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_PREFIX=agenthub_knowledge
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=REPLACE_WITH_VERIFIED_MODEL
EMBEDDING_DIMENSIONS=REPLACE_WITH_VERIFIED_DIMENSIONS
EMBEDDING_PIPELINE_VERSION=v1
JWT_SIGNING_KEY=REPLACE_WITH_HIGH_ENTROPY_SECRET
APP_PUBLIC_BASE_URL=http://localhost:3000
ALLOWED_ADMIN_ORIGINS=http://localhost:3000
ALLOWED_WIDGET_ORIGINS=http://localhost:3000,http://localhost:5500
MAX_CHAT_IMAGE_BYTES=5242880
MAX_DOCUMENT_BYTES=10485760
# Next.js public only
NEXT_PUBLIC_APP_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_PATH=/api/v1
```
Never commit live `.env`; provide `.env.example` and check missing env at startup. Same-origin route `/api/v1` forwarded to `localhost:8000` for browser cookies/SSE; Next server can call internal backend URL and forward cookies server-side. Verify CORS/CSRF/HTTPS cookies based on local/prod mode explicitly.

## Local startup target
1. Supply and validate required env, provision private/public buckets and a non-production Qdrant endpoint; verify configured embedding dimensions against the selected model/profile.
2. Run Alembic migrations; create minimal safe seed shop/products/document only for dev with label.
3. Run persisted ingestion runner, FastAPI, Next.js; static external HTML at a different local port to test embed.
4. As features land, expand the smoke sequence: login → workspace(shop) → agent(chatbot) → product/doc → playground → publish → embedded widget → conversation. Foundation acceptance requires only the local health/scaffold and migration harness; test later capabilities once implemented.
5. Run lint/typecheck/unit/integration/e2e; verify no secrets in web bundle/network panel.

## VPS future
Docker Compose services `web`, `api`, `worker`, `reverse-proxy`, plus Qdrant only if the later deployment decision selects self-hosting; Supabase DB/Storage remain managed unless an ADR changes. Reverse proxy TLS, websocket unnecessary for SSE, disable event-stream buffering. Health/readiness, restart policy, backup/rebuild and recovery, env/secret injection, log rotation, rate limiting, migration-on-deploy **single runner** and rollback plan. Avoid automatic destructive schema migration on every container startup.
