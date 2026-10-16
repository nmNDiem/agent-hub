# Channel provider references

These files contain deep provider-specific protocol detail. Do not read both for a generic Channel or Conversation change.

- Load [`facebook.md`](facebook.md) only for Facebook connection, credential, webhook, media, response-window or delivery work.
- Load [`zalo.md`](zalo.md) only for Zalo OAuth/refresh, credential, webhook, media, response-window or delivery work.

Shared Channel behavior belongs to [`../../domains/channels.md`](../../domains/channels.md); cross-cutting HTTP/event conventions belong to [`../../api.md`](../../api.md); deployment/provider setup belongs to the relevant section of [`../../operations.md`](../../operations.md).
