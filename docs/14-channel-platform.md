# 14 — Omnichannel integration design

## Coverage
**MVP:** website widget. **Later:** Facebook Messenger and Zalo via officially supported APIs subject to platform access, permissions, policy and product feasibility. Never assume all channels offer the same features or message types.

## Contract for each adapter
Input: `provider`, `connection_id`, stable external message/event ID, external user/thread ID, message timestamp, text, attachment metadata and verified authenticity. Output: tenant-scoped normalized inbound message. Outbound: channel-specific text/cards/attachments mapped from normalized answer with capability-aware fallback.

## Inbound flow
1. Receive webhook at channel-specific endpoint; validate vendor challenge/signature/token and payload size.
2. Resolve connection -> workspace/agent, with no trust in tenant metadata supplied by sender.
3. Deduplicate vendor event by unique `(provider, connection_id, external_event_id)`; tolerate reordering.
4. Persist message before processing; avoid duplicate model charges on retries.
5. Enforce user opt-outs, per-channel permissions and platform messaging windows.
6. Generate answer; deliver with bounded retries/dead-letter and observable delivery status.

## Web widget MVP
Origin allowlist is a defense-in-depth signal, **not** a secret. Public embed key maps only to published agent; short-lived session and throttling protect conversation endpoints. No auth cookie required for visitors. The visitor's image is uploaded privately with size/type/TTL controls and scoped to that conversation.

## Future capabilities and constraints
Connection setup/revoke, token storage encryption, webhook verification, multi-tenant mapping, reconnect/re-auth, template approval where platform requires, message window handling, media download quarantine, unsubscribe/handoff, message edits/deletes if supported. Store only necessary platform metadata; never log access tokens. Maintain manual fallback when a vendor endpoint is unavailable.

## Release gates per channel
Document official vendor prerequisites and permitted use; obtain account permissions; implement contract and signature tests; confirm retention/privacy and consent; check channel rendering on real devices; run a pilot; record failure and disconnect behavior. Do not schedule Facebook/Zalo implementation as part of F0–F5.
