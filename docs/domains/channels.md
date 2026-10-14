# Channels

## Purpose

Channels connect external messaging surfaces to the shared conversation system. Website, Facebook Messenger and Zalo are first-class AgentHub channels, not separate chatbot products.

## Current capability

The Website channel is complete: published configuration, exact-origin policy, scoped anonymous sessions, SSE, transcript restore, image upload, product cards, consented lead capture and safe contact CTA.

M1.1 adds the implemented shared foundation:

- tenant-scoped `web | facebook | zalo` connections and one active agent/revision binding per connection;
- Website presentation configuration separated from connection and binding state;
- normalized inbound/outbound contracts and capability-aware evidence fallback;
- verified-event deduplication, connection-scoped external thread/message mappings and ordering tolerance;
- durable outbound delivery with leases, fencing, bounded retry and terminal failure;
- explicit conversation lifecycle, workflow status and `ai | human | paused` handling mode;
- a credential-vault contract with only opaque credential references persisted.

## Current delivery

M1.2 adds Facebook Messenger on the shared foundation:

- connection setup, health, reauthorization and revocation;
- encrypted provider credentials;
- Facebook webhook challenge/signature validation;
- server-side connection-to-workspace/agent resolution;
- supported inbound text/media and outbound answer rendering;
- Facebook capability/message-window/opt-out enforcement;
- delivery status visible to operators.

The completed M1.2 adapter uses the official Graph API and HTTPS Page webhooks. Owner/admin
connection validates app ownership, token/data-access expiry, `pages_messaging`, Page `MESSAGE`
task access and the expected Page before subscribing the `messages` field and binding a published
agent revision. Reauthorization accepts only the same Page, rotates its Vault credential and
best-effort revokes the previous secret. Health distinguishes healthy, expired permission,
reauthorization, webhook-subscription and unknown-delivery states.

Challenge and `X-Hub-Signature-256` validation happen before payload parsing or connection lookup.
Text and image events are persisted/deduplicated before acknowledgement. Audio, video and file
attachments are retained only as safe unsupported metadata. Image URLs are ephemeral worker input:
each HTTPS hop is allowlisted and bounded by redirect, timeout, bytes, decoded pixels and MIME;
sanitized bytes enter private Storage quarantine and the URL is cleared. Expired/failed objects
remain eligible for bounded cleanup.

A leased/fenced response job reuses the published grounded runtime, catalog/knowledge scope and
workspace quota, then atomically creates one outbound message and delivery. Duplicate webhook
delivery cannot schedule another model turn. Exact `stop | unsubscribe | dừng | hủy đăng ký |
không nhận tin` and `start | subscribe | bắt đầu | đăng ký | nhận tin` commands control thread
automation after whitespace trim and case-folding. Sends use `messaging_type=RESPONSE` only while
the latest inbound message is within 24 hours. Message tags, marketing and proactive messages are
not supported.

Outbound work runs in a dedicated channel worker over the shared durable delivery queue. Explicit
rate-limit/transient rejections use bounded retries. Ambiguous timeout, connection and HTTP 5xx
results stop as `FACEBOOK_DELIVERY_UNKNOWN` for operator reconciliation because Meta's verified
contract does not provide an idempotency key that would make automatic replay duplicate-safe.

M1.3 adds Zalo OA OAuth v4 with PKCE, one-time user/workspace/agent-bound state and server-side
access/refresh token storage. The authorization callback validates the returned OA identity;
reauthorization must return the same OA. Refresh runs under a locked connection because each
refresh token is rotated, then replaces the Vault bundle and best-effort removes the old secret.
OAuth does not provide the OA webhook signing secret, so an owner/admin supplies that separate
secret once after authorization; the connection is not healthy until it is stored in Vault.

Zalo `X-ZEvent-Signature` verification uses the bounded raw payload, configured app ID, event
timestamp and connection-specific OA secret. A bounded OA-ID candidate lookup may occur solely to
retrieve verification material; no tenant message processing happens until the signature passes.
Text, image, audio, video, file, sticker and link events normalize into shared messages and media
metadata. Shared response and delivery jobs dispatch by provider. Zalo sends customer-service text
only within 48 hours of the latest verified inbound event; proactive, broadcast, transactional and
paid message classes are not supported.

## Boundaries

- Adapters translate provider payloads; they do not implement independent agent reasoning.
- The conversation service owns normalized messages and workflow state.
- Contacts own consented identity relationships; channel external IDs stay namespaced by provider and connection.
- The agent response remains channel-neutral text plus structured evidence. Each adapter renders the supported subset safely.
- Feature parity is not assumed. Unsupported cards/attachments use an explicit fallback.
- Shared webhook services accept only adapter-verified envelopes. Raw bodies and signature
  rules remain inside provider adapters.
- Website uses the shared connection, binding, conversation and message model while retaining
  its origin/session authorization, quota, image and SSE transport behavior.

## Credential boundary

Connections persist an opaque `credential_ref`, never a provider token. The shared
`CredentialVault` contract defines store, resolve and revoke behavior. A production vault must
be configured before Facebook or Zalo accepts real credentials.

The approved production implementation is Supabase Vault. `channel_connections.credential_ref`
contains a `supabase-vault:<uuid>` reference only. Supabase manages the project root key outside
the database; the application database role must have only the Vault access required by the
server adapter. A local revoke takes effect before best-effort provider unsubscribe/secret
deletion, so a provider outage cannot leave inbound processing enabled.

Zalo OAuth verifier, token bundle and OA webhook secret are separate secret values but are all
server-only Vault material.

Provider transport and webhook contracts belong in [`../api.md`](../api.md).
