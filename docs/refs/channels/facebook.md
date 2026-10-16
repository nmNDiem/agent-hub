# Facebook Messenger reference

Status: **CURRENT provider-specific contract.** Load only for Facebook connection, webhook, media, response-policy or delivery changes. Generic Channel ownership and invariants remain in [`../../domains/channels.md`](../../domains/channels.md); shared API conventions remain in [`../../api.md`](../../api.md).

## Management routes

- `GET|POST /api/v1/workspaces/{workspace_id}/channels/facebook` — owner/admin listing and Page connection.
- `POST /api/v1/workspaces/{workspace_id}/channels/facebook/{connection_id}/health` — validate token and repair Page webhook subscription.
- `POST /api/v1/workspaces/{workspace_id}/channels/facebook/{connection_id}/reauthorize` — rotate the same Page's Vault credential.
- `DELETE /api/v1/workspaces/{workspace_id}/channels/facebook/{connection_id}` — local-first revocation.
- `GET|POST /api/v1/webhooks/facebook` — Meta challenge and signed event delivery.

Responses expose safe Page identity, Agent binding, lifecycle/health timestamps and bounded queue/delivery state—never Page tokens or Vault references.

## Connection and credentials

Connection validates app ownership, token/data-access expiry, `pages_messaging`, Page `MESSAGE` task access and expected Page identity before subscribing to `messages` and binding a published revision. Reauthorization accepts only the same Page, installs the new Vault secret and best-effort revokes the prior secret. Health distinguishes permission expiry, reauthorization need, webhook-subscription failure and unknown delivery.

Production uses Supabase Vault through opaque credential references. Local revocation takes effect before provider unsubscribe or secret deletion.

## Webhook and media

- Validate Meta challenge and `X-Hub-Signature-256` over the bounded raw body before payload parsing or connection lookup.
- Persist/deduplicate text and image events before acknowledgement.
- Retain audio/video/file attachments only as safe unsupported metadata.
- Treat image URLs as ephemeral worker input: every HTTPS hop is allowlisted and bounded by redirect, timeout, bytes, decoded pixels and MIME.
- Store sanitized bytes in private quarantine, clear provider URLs after fetch/failure and keep failed objects eligible for bounded cleanup.

## Response and opt-out policy

A leased/fenced response job reuses the published runtime, authorized Catalog/Knowledge scope and workspace quota, then atomically creates one outbound message and delivery. Duplicate events cannot schedule another model turn.

Exact supported subscribe/unsubscribe keywords control thread automation after whitespace normalization and case-folding. Send `messaging_type=RESPONSE` only within 24 hours of the latest verified inbound message. Message tags, marketing and proactive messages are not supported.

## Delivery certainty

Send through the official Graph API using server-resolved Page credentials and connection-scoped PSID. Definite rate-limit/transient rejections may retry. Timeout, transport, malformed success and HTTP 5xx outcomes become terminal `FACEBOOK_DELIVERY_UNKNOWN` because replay may duplicate a reply whose provider response was lost.

## Required verification

Use fake Graph/Vault adapters in automated tests. Cover challenge/signature failure, raw-body size, Page/workspace isolation, duplicate/reordered events, response-job fencing, opt-out, 24-hour enforcement, media bounds, cleanup, same-Page credential rotation, receipts and ambiguous delivery. Live Page/App review remains an explicit non-production manual procedure in [`../../operations.md`](../../operations.md).
