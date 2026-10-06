# Channel architecture: Web first, social later

## Core adapter interface
```python
class ChannelAdapter(Protocol):
    async def validate_inbound(self, headers, body) -> InboundEvent: ...
    async def normalize(self, event) -> ChatInput: ...
    async def deliver(self, conversation, reply) -> None: ...
```
`ChatInput` includes workspace_id, agent_id, channel, external conversation/message IDs (strings), text, media references and idempotency key. Core chat and RAG are channel-neutral; their reply combines validated conversational text with structured product cards and source references. Web SSE can render cards visually, while a future social adapter can format the same authoritative fields as text or a provider-native template. Web SSE sends immediately; future social channels call provider deliver asynchronously. Provider credentials are encrypted at rest and never rendered to client; webhook requests verified with provider-specific signatures; deduplicate provider message IDs.

## Web flow
Loader has public bot UUIDv7 → server verifies published, allowed origin and quotas → safe config → anonymous bot-scoped session → `/public/.../messages:stream` → structured response. Strong rate limiting by IP/session/bot/shop, max concurrency and daily quota; allowlisted domains make casual unauthorized embedding harder but not a security boundary. Add abuse monitoring; do not promise absolute prevention of forged non-browser clients. Disable iframe embedding by unknown origins via CSP `frame-ancestors` or appropriate iframe transport. If using `postMessage`, validate origin and source window.

## Publish consistency
Store immutable bot revision; on widget session creation pin revision or select current on each new session, but document the choice and never change revision mid-turn. Draft tone and knowledge toggles must not leak to widget until publish. Safe public config contains greeting, theme, avatar, public bot ID, supported capabilities, disclosure—not internal source text or model credentials.

## Future social channel gates
Facebook/Zalo appear only as roadmap until verified adapter, webhook, provider authorization, account mapping, retry and delivery semantics exist. Provider-specific limits, file formats and policies must be verified at implementation time; no automatic parity claim with Web. Store external account ID as opaque text, not UUIDv7.
