# Screen: Conversations inbox

## Purpose and layout
Two-pane desktop: chatbot/period filters and conversation list ~320–380 px, selected thread remainder. The selected panel has session metadata, messages, safe attachment metadata and source/product evidence. Mobile transitions list → detail with back button. This local-pilot inbox is owner/admin-only and read-only.

## Conversation fields
Public UUIDv7, Web channel, anonymized visitor label, chatbot, started_at/last_message_at, last visitor preview, message_count and retention deadline. Avoid inventing customer identities from the widget's anonymous session. Cursor paging is stable by `(last_message_at DESC, public_id DESC)` and does not expose internal BIGINT IDs.

## Interaction rules
List selection changes URL and preserves the filter. Loading state and empty filtered result use `Không có hội thoại phù hợp`. Images render only validated type/dimensions/byte size—not private object keys, grants or URLs—and message text is never unsanitized model HTML. There is no resolve/reply/assignment/unread/SLA action. No fake Facebook/Zalo icons appear for Web conversations.

## Acceptance
No cross-shop thread access via guessed UUIDv7; no stale transcript after shop switch; pagination does not duplicate; failure leaves selected context with retry; long messages, image-only messages and streaming partial messages render correctly.
