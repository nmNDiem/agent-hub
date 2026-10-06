# Agent runtime, retrieval and vision

## Execution flow

1. Authenticate/verify the channel actor and resolve immutable workspace, agent revision and allowed scope.
2. Normalize message, locale and permitted attachments; apply abuse, concurrency and quota checks.
3. Persist/reuse the inbound message and idempotency identity.
4. Run bounded custom orchestration over allowlisted typed tools.
5. Query structured catalog facts and/or tenant-filtered knowledge as required.
6. Build server-owned instruction layers with retrieved/user/provider content explicitly treated as untrusted data.
7. Call the configured OpenAI adapter with bounded model/tool calls, tokens and timeout.
8. Validate tool output, product/source evidence and final response contract.
9. Persist response, evidence, usage and delivery work; render through the active channel adapter.

## Tool boundary

Implemented read tools include product search, product detail, availability and shop-knowledge search. Tool invocation receives a server-resolved immutable scope; model/browser parameters can only narrow it. Tools never expose arbitrary SQL, Storage paths or URL fetching.

Contact/handoff actions use separate consent/business validation and cannot be implied by generated prose. Future write tools require explicit side-effect classification, user confirmation, authorization, idempotency and audit.

## Catalog grounding

- Structured catalog records own product existence, SKU, options, price and inventory.
- Requested options must coexist on the same variant.
- Effective price and inventory are calculated at read time; unknown remains unknown.
- Products may have no variants, fashion options or size guide.
- Product cards are built by the server from validated tool results, not parsed from prose.

## Knowledge retrieval

- Retrieve only from allowed knowledge bases and active ready generations.
- Qdrant queries inject workspace/source/profile filters and returned chunk IDs are revalidated in PostgreSQL.
- Limit context size and include actual source locator/version information.
- A retrieval score is not truth; conflicting or absent evidence produces calibrated uncertainty.
- Embedding profiles are immutable by provider/model/dimensions/pipeline. Profile changes rebuild and atomically cut over rather than mixing vector spaces.

## Vision

- Accept only validated/re-encoded JPEG, PNG or WebP within byte/pixel/session limits.
- Keep images private and short-lived with single-use scoped attachment handles.
- Vision may describe clothing category, color, pattern/material and style cues; it does not perform identity or sensitive-person inference.
- Catalog matching is approximate and must disclose uncertainty or no-match.
- A photo cannot prove body fit, stock or product identity.

## Failure behavior

- Provider/model/retrieval failures do not corrupt conversations or source state.
- Recoverable malformed tool calls receive bounded correction feedback.
- If the runtime cannot safely answer, return a neutral channel-appropriate fallback and configured handoff option; do not expose internal codes or invent content.
- Automated tests use fake providers. Paid-service manual checks are owner-run and explicitly budgeted.
