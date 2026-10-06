# Channel adapter contract

## Shared model

Each channel adapter converts provider traffic into a normalized contract:

```text
InboundEnvelope
  provider
  connection_id
  external_event_id
  external_thread_id
  external_sender_id
  occurred_at
  text?
  attachments[]
  capabilities

OutboundEnvelope
  normalized_message_id
  connection_id
  external_thread_id
  text
  product_evidence[]
  source_evidence[]
  attachments[]
  idempotency_key
```

Provider SDK/payload types stay inside adapters. Core conversations store normalized content plus the minimal provider mapping needed for delivery/audit.

## Adapter responsibilities

- Validate webhook challenge/signature/token against the bounded raw request.
- Resolve an active connection and derive trusted workspace/agent scope.
- Normalize supported text/media without inventing unsupported parity.
- Deduplicate stable provider event IDs and tolerate reordering.
- Map external thread/sender/message identities under provider + connection namespace.
- Render normalized responses to provider-supported text, media or native templates.
- Persist delivery attempt/result and classify retryable versus terminal errors.
- Enforce provider permissions, opt-outs, messaging windows and rate limits.
- Expose connection health/re-authentication without exposing credentials.

## Website

- Public agent ID maps only to safe published configuration.
- Exact origin policy is defense in depth; an opaque short-lived session is the conversation authorization.
- Widget uses SSE, session-scoped product-image grants and private visitor images.
- Host CSS is isolated through the independent bundle/Shadow DOM; no privileged token appears in DOM or URLs.

## Facebook Messenger

The implementation task must verify current official platform prerequisites before code. The adapter design must cover Page identity/connection, webhook verification, stable event dedupe, supported attachments/templates, outbound delivery state, token revocation/re-authentication and provider messaging constraints. No fake connected state is allowed.

## Zalo

The implementation task must verify current official OA/API prerequisites before code. Keep OA identity, verification, payload/media types, delivery rules and provider error mapping inside the Zalo adapter. Differences from Facebook are explicit capabilities, not branches scattered through conversation services.

## Reliability

- Persist inbound events/messages before processing and outbound delivery before calling providers.
- Acknowledgement timing is separated from long-running AI work when required by a provider.
- Retry uses exponential backoff/jitter, max attempts and terminal/dead-letter visibility.
- Revoked/disconnected connections stop new processing safely without erasing historical normalized conversations.
- Media fetches use provider allowlists, strict size/time/type validation and private Storage; arbitrary payload URLs are never fetched.

## Required tests per adapter

- valid/invalid verification and signature;
- unknown/revoked/wrong-workspace connection;
- duplicate and reordered event;
- identical external IDs under different connections;
- media size/type/timeout failure;
- provider timeout/rate limit/terminal rejection;
- retry without duplicate model charge or outbound message;
- capability fallback and safe operator-visible status.
