# Screen: embeddable Website Chat Widget
Reference: `../../../assets/reference/03-website-chat-widget.png`.

## Core principle
Image contains a fictional **Lumé** storefront as host-page context. The product ships the widget and an optional isolated preview, **not a complete fashion-storefront clone**. A shop can embed it on its own website. Never hardcode Lumé, sample models, product cards or UUID-looking illustration text as live data.

## Client surfaces
- Launcher fixed to configurable bottom-right/left, 56 px default; visible while closed; unread indicator only for genuine unread events.
- Panel desktop about 380–420 px wide, 540–640 px max height, capped by viewport and safe areas; mobile full-screen/bottom-sheet with visible close, no content behind inaccessible overlay.
- Header: bot avatar/logo, display name, optional operating status **only if true**, minimize/close. Body: real greeting, suggested actions, transcript, product cards, image preview, privacy notice. Footer: input, upload, send/stop, optional provider attribution only when policy demands; no internal widget/bot ID displayed to shoppers.
- Theme: CSS custom properties generated from validated published brand settings; enforce contrast and fallback palette. The host storefront does not change the admin theme.

## Embed concept
```html
<script async src="https://YOUR_HOST/widget/v1/loader.js"
        data-bot-id="<PUBLISHED_BOT_UUIDV7>"></script>
```
Public ID is *not* an access key. On load fetch public, safe published config for the bot. Add allowed domains and a published flag at server; never put a privileged token, workspace ID, OpenAI key, or internal numeric IDs in loader. No `*` postMessage target; validate origins and iframe sender if using iframe isolation. During local testing, host and port can be configurable; deploy a script URL only once its host exists.

## Interaction flow
Open → fetch safe config → display greeting → generate anonymous short-lived bot-scoped session via server → send text/optional image → SSE stream → show schema-neutral structured product cards with server-validated effective price, inventory, generic options and safe image/link references → open product link restricted to shop-approved URL domains. Reopen preserves session only for the defined retention period; the user can `Xóa cuộc trò chuyện` and revoke the token. Consent/disclosure about AI and privacy is visible, not implied.

## States
Network offline with retry, API 429 cooldown, invalid domain/publish status unavailable (`Chatbot hiện không khả dụng`), streaming fallback, image upload failure, session expired create a new one with clear history handling. Use no fake `Online` state unless backend availability is verified. Enforce max widget message length, file bytes, requests, timeouts server-side.

## Widget acceptance
Embed script works on a static external test HTML page; host global CSS cannot break widget; no credentials exposed; cross-shop public_id cannot read private settings; invalid-origin requests blocked as a layer (origin alone is not security); mobile safe-area & keyboard handled; screen-reader can use open/close/send; actual product click goes to approved real URL; first reply is streamed.
