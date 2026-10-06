# Screen: Chatbot management

## Unified workbench
The selected chatbot appears once in a compact selector strip. Desktop keeps configuration at roughly 38% width and the real test conversation at roughly 62%; widths below 1024 px use `Cấu hình | Thử chatbot` tabs while preserving both drafts. Creation is an inline action above the workbench. The empty state encourages creating the first chatbot. A separate Playground page is not part of the active information architecture.

## Create/edit wizard
1. Basics: name, description, use case (`Tư vấn thời trang`), language, welcome message.
2. Knowledge: choose catalog, FAQs/policies, uploaded documents that are `ready`.
3. Behavior: brand voice, response length, fallback statement, image understanding (only if selected model supports it).
4. Widget: avatar, primary color, launcher position, CTA text and permitted website origins.
5. Test in the workbench beside the configuration. `Xuất bản` creates immutable revision/snapshot; other users see **only published** configuration. Settings edited afterwards stay draft until republished.

## Guardrails
Model picker only offers supported configured OpenAI models from backend; no screenshot's outdated fixed model string. Bot public_id is unprefixed canonical UUIDv7 in URLs/API; optional `bot_` cosmetic prefix seen in image is **not** stored or copied. Validate URL allowlist. Archive bots rather than cascading destructive deletion of conversations. Bot creation and publishing require owner permission once implemented.
