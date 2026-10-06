# 07 — UX flows (fashion shop MVP)

## Shop-owner first run
`Landing -> Register/email verify -> Create workspace/shop -> Enter shop details -> Import catalog or add products -> Enter policy/FAQ and size guidance -> Create/configure agent -> Configure widget branding + allowed website origin -> Preview with test questions/images -> Publish -> Copy embed snippet -> See conversations/leads/usage`.

### Owner dashboard navigation
- Overview: real 7/30-day conversation/reply activity, active Web chatbots, recent conversations/leads and workspace-local monthly generation/vision usage.
- Catalog: list/search/filter products; detail with variants, generic options/attributes, images and inventory state; manual edit; CSV/XLS/XLSX Analyze → Resolve → Diff → Commit import flow.
- Knowledge: shop profile, FAQ/policy, PDF/TXT uploads, indexing states and error recovery.
- Agents: editable greeting and personality/style instructions, grounding policy, publish/pause, provider usage information (not model selection UI at first). New agents receive useful locale-aware defaults and require only a name before their first Playground test.
- Channels > Web: implemented in the chatbot workbench with branding, exact origin allowlist, readiness, responsive preview, publish/pause and embed snippet.
- Conversations: owner/admin read-only paginated Web threads with chatbot/period filters, safe attachment metadata and clearly labeled visitor-provided information; no staff reply, assignment, unread or SLA controls.
- Leads: consented contacts, callback status and safe CSV export (authorized roles only).
- Settings: workspace, owner account/password, basic member configuration if enabled.

## Visitor chat
`Open widget -> Welcome + example prompts -> Anonymous message -> Streaming reply -> Optional product cards -> Open shop product URL -> Ask variant/size -> Optional photo -> Similar existing products -> Optional consented contact -> Human contact CTA`.

### Empty/loading/error states
- No catalog: owner sees import CTA; visitor hears assistant cannot verify products yet.
- Pending knowledge ingestion: display indexing state and do not imply updated docs are searchable.
- Model timeout: non-technical retry message and shop contact option; no fake answer.
- Unknown stock: "Chưa có thông tin tồn kho chính xác; shop có thể xác nhận giúp bạn.".
- Missing size chart: no invented recommendation; ask shop or offer general non-definitive advice.
- Image mismatch: show tentative candidates or honest no-match.
- Quota exceeded: user-friendly limit notice before a provider call; owner sees the shared Widget + Playground monthly quota and observed usage without a cost estimate.

## Widget UX checklist
- Keyboard/mobile usable; minimize CSS collisions with host page; clear focus and accessible labels.
- Theme color and corner position are editable in the Web channel panel; display name/greeting come from the agent configuration. Arbitrary executable HTML is never accepted.
- Anonymous session has visible privacy information; optional consent before saving a lead.
- Do not make customers log in just to ask about clothing; retain/resume history only for same visitor session.
- Product card: safe image reference, title, up-to-date effective price, availability qualifier, relevant generic options and shop product link. Do not require fashion-only fields.
- Support concise Vietnamese first; allow later localization without hard-coded Vietnamese-only DB columns.

## MVP handoff
Display configured shop contact CTA or collect a callback request. Do not label as a staffed live chat without staffing capability. Full agent inbox deferred.
