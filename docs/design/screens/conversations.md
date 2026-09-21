# Screen: Conversations inbox

## Purpose and layout
Two-pane desktop: search/filter and conversation list ~320–380 px, selected thread remainder. Toolbar with channel, status, bot, period, keyword filters; selected panel has session metadata, messages, attachments and source/product evidence if permissions allow. Mobile transitions list → detail with back button.

## Conversation fields
Public UUIDv7, channel, anonymized visitor display name, bot, started_at/updated_at, last preview, state `open | resolved`, message_count, optional handoff flag (future), `unread` if tracked. Avoid inventing customer identities from widget's anonymous session. Cursor paging by `(last_message_at, id)`; UI shows local times and accessible ISO tooltip.

## Interaction rules
List selection changes URL, preserves filter. Loading thread skeleton, empty filtered result `Không có hội thoại phù hợp`. Render attachments via short-lived authorized URLs; never render unsanitized model HTML. Owner may mark resolved if API implements state change; F0 inbox read-only is acceptable with status action hidden. No fake Facebook/Zalo icons for web conversations.

## Acceptance
No cross-shop thread access via guessed UUIDv7; no stale transcript after shop switch; pagination does not duplicate; failure leaves selected context with retry; long messages, image-only messages and streaming partial messages render correctly.
