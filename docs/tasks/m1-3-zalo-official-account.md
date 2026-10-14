# Zalo Official Account integration

## Goal

Deliver a production-shaped Zalo Official Account channel with end-to-end OAuth, automatic
token refresh, verified inbound webhooks, supported media ingestion, shared response-job
processing, outbound text delivery, revocation, health reporting, and operator UI.

## Acceptance criteria

- An owner or admin can authorize an eligible published agent through Zalo OAuth v4 without
  copying access or refresh tokens into AgentHub.
- OAuth uses PKCE and a short-lived, single-use, user/workspace/agent-bound state. Callback
  replay, expiry, denial, wrong-user use, and cross-workspace access fail safely.
- Tokens and the OA webhook signing secret are stored only in the server-side credential vault.
  Expiring tokens are refreshed automatically with concurrency protection; terminal refresh
  failures require OAuth reauthorization.
- Zalo webhooks are verified over the bounded raw request body before tenant-owned business
  data is processed. Inbound events are persisted and deduplicated before response work is
  enqueued.
- Text and supported image, audio, video, file, sticker, and link events normalize into the
  shared channel contracts. Unsupported or malformed events fail explicitly without leaking
  payload contents.
- Outbound assistant text is delivered through the shared response/delivery pipeline and a
  Zalo-only adapter. Automatic replies are limited to verified conversations whose latest
  inbound message is within 48 hours.
- Operators can connect, finish webhook-secret setup, inspect health, reconnect, and revoke a
  Zalo OA from the chatbot workbench.
- Every new tenant-owned resource has negative cross-workspace coverage. Provider traffic is
  faked in automated tests.

## Confirmed decisions

- OAuth is the only token-acquisition and reauthorization flow; there is no manual token form.
- Zalo tokens use OAuth v4 authorization-code plus PKCE and are refreshed by the backend.
- The provider does not return the OA webhook signing secret through OAuth, so the UI collects
  that separate secret once after authorization and stores it in the same vault bundle.
- The OAuth callback redirects only to the configured AgentHub dashboard origin and a fixed
  path; it never accepts a client-provided return URL.
- Automatic outbound is restricted to the conservative 48-hour reply window. Broadcast,
  transactional, welcome, and other proactive messages are out of scope.
- Shared response jobs dispatch by provider; Facebook- and Zalo-specific limits and error
  mapping remain isolated in their adapters/policies.

## Data, API, UI, and security impact

- Add durable, expiring channel OAuth attempts containing only a state hash and a vault
  reference for the verifier; bind each attempt to its initiating member and target agent.
- Extend usage-event surface constraints for Zalo and add the indexes/constraints required for
  safe OAuth consumption and provider-account uniqueness.
- Add authenticated Zalo connection, OAuth-start, webhook-secret, health, and revoke endpoints;
  add a public OAuth callback and verified webhook endpoint.
- Add a Zalo channel panel to the existing chatbot workbench, reusing the established channel
  presentation and feedback patterns.
- Permit only a bounded provider-account lookup before Zalo signature verification so the
  server can obtain that OA's signing material; no tenant business processing is allowed until
  verification succeeds.

## Test plan

- Unit-test OAuth URL/PKCE construction, one-time state consumption, callback failures, token
  exchange, identity validation, same-OA reauthorization, vault rotation, and refresh locking.
- Unit-test webhook signatures, duplicate events, normalization, supported/unsupported media,
  48-hour enforcement, provider-aware response dispatch, delivery retry classes, revocation,
  redaction, and negative cross-workspace authorization.
- Exercise migrations against the optional isolated PostgreSQL test database.
- Run API Ruff, mypy, and targeted/full pytest plus web lint, typecheck, and Vitest after the
  implementation is complete.

## Documentation impact

- Update the channel domain, API, data model, security, UI, testing/operations guidance, and
  environment example once with the final contracts and manual Zalo Console setup steps.
- Mark M1.3 complete in the roadmap only after verification succeeds.

## Out of scope

- Broadcasts, templates, transactional messages, paid message classes, welcome messages,
  comments, calls, group chat, commerce mutations, and automated Zalo Console configuration.
- Unified inbox/handoff, contact timeline, and analytics work assigned to later M1 deliveries.
