# Channels

## Purpose

Channels connect external messaging surfaces to the shared conversation system. Website, Facebook Messenger and Zalo are first-class AgentHub channels, not separate chatbot products.

## Current capability

The Website channel is complete: published configuration, exact-origin policy, scoped anonymous sessions, SSE, transcript restore, image upload, product cards, consented lead capture and safe contact CTA.

## Current delivery

M1 adds the shared social-channel foundation, Facebook Messenger and Zalo:

- connection setup, health, reauthorization and revocation;
- encrypted provider credentials;
- provider webhook challenge/signature validation;
- server-side connection-to-workspace/agent resolution;
- normalized inbound text/media and outbound answer rendering;
- event/message deduplication, ordering tolerance and durable retry;
- provider capability/message-window/opt-out enforcement;
- delivery status visible to operators.

## Boundaries

- Adapters translate provider payloads; they do not implement independent agent reasoning.
- The conversation service owns normalized messages and workflow state.
- Contacts own consented identity relationships; channel external IDs stay namespaced by provider and connection.
- The agent response remains channel-neutral text plus structured evidence. Each adapter renders the supported subset safely.
- Feature parity is not assumed. Unsupported cards/attachments use an explicit fallback.

Provider transport and webhook contracts belong in [`../api.md`](../api.md).
