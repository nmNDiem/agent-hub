# Screen: Chatbot management

## List
Cards/table with name, purpose, draft/published status, published_at, attached knowledge count, Web embed availability and quick actions `Cấu hình`, `Playground`, `Mã nhúng`. Search by name, server paging when needed. Empty state encourages creating first bot.

## Create/edit wizard
1. Basics: name, description, use case (`Tư vấn thời trang`), language, welcome message.
2. Knowledge: choose catalog, FAQs/policies, uploaded documents that are `ready`.
3. Behavior: brand voice, response length, fallback statement, image understanding (only if selected model supports it).
4. Widget: avatar, primary color, launcher position, CTA text and permitted website origins.
5. Test in Playground. `Xuất bản` creates immutable revision/snapshot; other users see **only published** configuration. Settings edited afterwards stay draft until republished.

## Guardrails
Model picker only offers supported configured OpenAI models from backend; no screenshot's outdated fixed model string. Bot public_id is unprefixed canonical UUIDv7 in URLs/API; optional `bot_` cosmetic prefix seen in image is **not** stored or copied. Validate URL allowlist. Archive bot rather than cascaded destructive deletion of conversations. Bot creation and publishing are owner-only in F0.
