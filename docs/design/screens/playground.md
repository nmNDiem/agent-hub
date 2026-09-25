# Screen: Chatbot Playground
Reference: `../../../assets/reference/02-chatbot-playground.png`.

## Goal
Owner tests the real backend assistant against the shop's approved knowledge before publishing. Playground **not** a fictional demo and **not** a production shopper session.

## Desktop layout
- Breadcrumb `Chatbot / [Tên chatbot] / Playground`; assistant name + status; top-right `Lưu cấu hình` and `Xuất bản` only when available.
- Left ~36–40%: assistant selector, `Tên / Mô tả`, tone options, knowledge source switches, preset prompts, model label read-only unless allowed. Keep scroll independent from chat where possible.
- Right ~60–64%: chat transcript with user/assistant bubbles, product recommendation cards, source chips and `Nguồn được sử dụng` drawer/panel; fixed input with upload image button, send and stop-generation.
- On widths <1024 px use tabs `Cấu hình | Thử chatbot`, preserve unsent message and settings draft; on mobile full-width transcript.

## Functional specification
1. Choose bot; fetch bot draft config, read enabled knowledge sources. UI must not turn documents into enabled sources until ingestion status `ready`.
2. Change draft tone/source toggles; dirty badge and `Lưu thay đổi`; explicit test-mode label: `Đang thử bản nháp` and distinguish published version.
3. Suggested prompts are buttons to populate input, not auto-submit unless clearly indicated. Send question or one image + optional question; client validates file then backend enforces.
4. Stream actual assistant response (SSE), render structured product suggestions from tool output and retrieved sources from backend. `Dừng` aborts request and displays retained partial reply.
5. `Làm mới hội thoại` clears **playground-local** transcript after confirmation; does not delete live shopper conversations. Option `Thử từ đầu` can create a new test session.
6. `Xem trên website` opens same widget configuration in isolated preview; never treat preview as public deployment.

## Product response example
In fashion demo ask `Tư vấn váy đi biển size M`; the tool maps `Size=M` to a generic option and may surface products **only** when the same allowed database variant satisfies all requested options. Display actual name, relevant option labels, effective price and explicit inventory qualifier (hide or label unknown facts). The same response/card schema must also handle products without variants or fashion options. Size charts appear only when sourced from a size-guide document or product metadata. Image input shows thumbnail + remove and short alt text; AI results distinguish uncertain visual features and avoid definitive fit claims from a photo.

## States and protection
Bot not found/other workspace -> 404 or 403; LLM disabled -> explanatory state; empty knowledge -> message `Chưa có dữ liệu`; no citations -> hide panel; upload error -> retry; rate limit -> retry hint; streaming lost -> partial response plus retry. Keep workspace ID + agent ID in every query key. No OpenAI key or system prompt leaked in client response.

## Playground acceptance
True end-to-end chatbot response; source IDs valid and shop-scoped; product cards link existing products; config unsaved warning; reloading bot preserves saved config; upload rejection visible; reset only test history; keyboard + screen-reader transcript.
