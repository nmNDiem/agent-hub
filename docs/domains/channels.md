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
`CredentialVault` contract defines store, resolve and revoke behavior. A production vault and
key-management choice must be approved and implemented before Facebook or Zalo accepts real
credentials.

Provider transport and webhook contracts belong in [`../api.md`](../api.md).
