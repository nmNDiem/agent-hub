# Channels

## Function and ownership

Channels adapt external transports to the shared conversation model. Website, Facebook Messenger, and Zalo are adapters, not separate agent products. Adapters own provider verification/rendering; Conversations owns normalized workflow; Contacts owns identity relationships.

## CURRENT

- Website publication, exact-origin policy, anonymous scoped sessions, streaming/replay, images, evidence cards, and consented lead capture.
- Tenant-scoped Website/Facebook/Zalo connections with one active agent/revision binding.
- Verified webhooks, connection-scoped deduplication/mappings, durable outbound delivery, bounded retries, health/revocation, and capability-aware fallback.
- Facebook Page validation, Graph API messaging, 24-hour response-window enforcement, opt-out handling, and bounded private image quarantine.
- Zalo OA OAuth v4 with PKCE/rotating refresh, separately stored webhook secret, signature verification, and 48-hour customer-service window enforcement.
- Supabase Vault references for production social credentials; secret values are never returned by application APIs.

Main data: connections/bindings, OAuth attempts, Website config, webhook events, provider mappings, delivery/receipt records, response jobs, and inbound-media metadata. Main surfaces: channel setup/health and the shared Inbox.

## Core flow

Verify raw provider request → resolve server-owned connection and tenant → normalize/deduplicate inbound event → persist message and response job → run the bound published Agent if policy allows → persist outbound message/delivery → adapter renders supported content → recheck provider window/opt-out → send and record outcome.

## Invariants

- Authenticity is verified before tenant processing or paid model work.
- A retry cannot create a second normalized message, model turn, or delivery identity.
- Raw payloads, tokens, temporary media URLs, and private object keys do not enter general DTOs/logs.
- Provider limits and opt-outs are enforced independently of model output.
- Ambiguous provider delivery is surfaced as unknown when replay is not duplicate-safe.
- Unsupported evidence/media has an explicit safe fallback; parity is not assumed.

## APPROVED DIRECTION

Additional channels reuse the normalized contracts only where their verified provider semantics fit. Each adapter documents authentication, identity namespace, capabilities, response window, idempotency, delivery certainty, media policy, revocation, and retention.

## NOT IMPLEMENTED

No proactive marketing/broadcast engine, arbitrary provider adapter framework, or assumption of staffed live service exists.

## Change trigger

A new provider starts with a concrete adapter contract and threat model; shared abstractions change only after repeated proven needs.

Related authority: [`conversations.md`](conversations.md), [`contacts.md`](contacts.md), [`../api.md`](../api.md), [`../security.md`](../security.md).
