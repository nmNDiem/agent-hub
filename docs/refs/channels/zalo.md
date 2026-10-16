# Zalo OA reference

Status: **CURRENT provider-specific contract.** Load only for Zalo authorization, webhook, media, refresh, response-policy or delivery changes. Generic Channel ownership and invariants remain in [`../../domains/channels.md`](../../domains/channels.md); shared API conventions remain in [`../../api.md`](../../api.md).

## Management routes

- `GET /api/v1/workspaces/{workspace_id}/channels/zalo` — scoped connection status.
- `POST /api/v1/workspaces/{workspace_id}/channels/zalo/oauth/start` — create a PKCE authorization URL.
- `GET /api/v1/channels/zalo/oauth/callback` — consume the authenticated one-time OAuth callback.
- `PUT /api/v1/workspaces/{workspace_id}/channels/zalo/{connection_id}/webhook-secret` — accept the separate write-only OA signing secret.
- `POST /api/v1/workspaces/{workspace_id}/channels/zalo/{connection_id}/health` — verify connection health.
- `DELETE /api/v1/workspaces/{workspace_id}/channels/zalo/{connection_id}` — local-first revocation.
- `POST /api/v1/webhooks/zalo` — signed OA events.

The start response exposes only authorization URL and expiry. Callback redirects use the configured AgentHub origin and existing fixed chatbot callback path. Responses never expose tokens, OA secret or Vault references.

## OAuth and credentials

OAuth v4 uses PKCE plus one-time user/workspace/Agent-bound state. The state hash expires after ten minutes and is consumed before provider exchange. Callback validates returned OA identity; reauthorization must return the same OA.

Refresh runs under a locked connection because each refresh token rotates, then installs the new Vault bundle and best-effort removes the old secret. OAuth does not supply the OA webhook signing secret, so owner/admin submits it separately. A connection is not healthy until that secret is protected in Vault.

## Webhook and media

Zalo `X-ZEvent-Signature` verification uses the bounded raw payload, configured app ID, event timestamp and connection-specific OA secret. The adapter may parse bounded app/OA identity solely to find candidate verification material; it performs no tenant normalization or persistence before signature success.

Text, image, audio, video, file, sticker and link events normalize into shared messages and bounded media metadata. Provider URLs and raw payloads do not enter public DTOs or routine logs.

## Response and delivery policy

Shared response/delivery jobs dispatch through `POST https://openapi.zalo.me/v3.0/oa/message/cs` using server-resolved credentials and a connection-scoped user ID. Customer-service text is at most 2,000 characters and is sent only within 48 hours of the latest verified inbound event. Proactive, broadcast, transactional and paid message classes are not supported.

Authentication failure requires OAuth reconnect. Definite rate-limit/transient failures use bounded retry; ambiguous external outcomes stop terminally instead of risking duplicate replies.

## Required verification

Use fake Zalo/Vault adapters in automated tests. Cover PKCE/state binding, callback replay, same-OA reauthorization, token rotation/refresh locking, invalid signature, event deduplication, workspace isolation, response-window/opt-out enforcement and ambiguous delivery. Live OA authorization/sending remains an explicit non-production manual procedure in [`../../operations.md`](../../operations.md).
