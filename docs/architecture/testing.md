# Verification matrix

| Layer | Required tests |
|---|---|
| IDs | generated UUID.version=7; BIGINT identity insert; no uuidv4/default v4 regressions; copy/public IDs round-trip |
| Auth | signup/login/logout/refresh rotation/reuse; generic failures; cookie attrs, CSRF, redirect safety |
| Tenancy | shop A member cannot list/get/mutate shop B bot, conversation, product, doc or Storage asset; cross-shop RAG fixture |
| DB | Alembic upgrade on clean DB, unique constraints, FK match, deletion/archival and tenancy indexes |
| AI | fake-provider deterministic stream, timeout/abort/retry, actual source IDs only, no hallucinated product, image reject |
| Knowledge | MIME/size/signature, corrupt PDF, no-text PDF, retries/idempotency, remove revokes chunks, no partial ready |
| Widget | published vs draft, invalid origin, brute-force quota, session binding, mobile focus/host CSS isolation |
| UI | user journeys, empty/error/loading, shop switching, filter URL, voice of Vietnamese strings, contrast/responsive |
| Ops | health, secret redaction, per-shop token cap, metric definitions and log request IDs |

## Test fixture protocol
Never use mockup `bot_0198...` strings as real IDs. Generate UUIDv7 at fixture creation, seed 2 workspaces with similar product names and 2 agents to prove isolation. Internal BIGINTs left to DB identity. Fake OpenAI adapter keeps offline tests free/fast; opt-in real-provider smoke test explicitly budgeted and never used as mandatory CI.

## Demo is not done
A pretty static dashboard without local boot, migration harness and working test tools does **not** pass F0. Real auth and tenant isolation are F1 gates. A hardcoded AI reply does not pass F3. Simulated `Connected` Facebook/Zalo badges do not count as channels. Reference images are layout targets, not functional acceptance evidence.
