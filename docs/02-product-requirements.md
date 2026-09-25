# 02 — MVP requirements and acceptance criteria

Priority notation: P0 = required to launch pilot, P1 = useful after stable pilot, D = deferred.

| ID | Priority | Feature | Acceptance criteria |
|---|---|---|---|
| AUTH-01 | P0 | Register/login/logout | Email/password; hashed passwords; generic login failure; logout revokes refresh session; verified email or explicitly controlled verification bypass in local dev |
| AUTH-02 | P0 | Recover password | One-time, expiring reset; session revocation after reset; no account enumeration |
| TEN-01 | P0 | Workspace ownership | Registration creates/joins workspace; all workspace APIs verify membership/role; cross-tenant negative tests |
| AGT-01 | P0 | Website agent config | Owner edits assistant name, greeting, instructions within safe bounds, status; only published agent usable by widget |
| KB-01 | P0 | Shop knowledge | Owner edits shop summary, FAQ, return/shipping policy, size guidance; upload PDF/TXT with safe parsing; status per ingestion job |
| CAT-01 | P0 | Catalog | Add/edit/archive products + optional variants, generic options/attributes, images, title, description, category, price/currency, optional inventory and size table; CSV/XLS/XLSX staged import with validation/diff/result report |
| CAT-02 | P0 | Catalog answers | Server tools provide product/variant/source IDs; latest known DB price/stock; no fabricated sizes/availability |
| CHAT-01 | P0 | Anonymous widget | Embedded on allowlisted shop origin; visitors can begin a scoped conversation without shop login; rate limit; reloading resumes only their session |
| CHAT-02 | P0 | Streaming replies | SSE event sequence and graceful fallback; client renders answer and source/product cards; handles timeout/provider error |
| CHAT-03 | P0 | Visitor image | Safe image upload (file/type/size checks); vision-capable provider describes salient clothing features; related catalog results or calibrated no-match |
| LEAD-01 | P0 | Opt-in leads | User can choose to give name/email/phone; consent and provenance stored; no mandatory lead wall |
| HAND-01 | P0 | Human follow-up | CTA to shop-approved contact URL or callback request; no false promise of live operator |
| DASH-01 | P0 | Dashboard | Products, knowledge, agent config/embed snippet, conversations, leads, minimal usage metrics |
| OBS-01 | P0 | Operations | Redacted logs, request IDs, sensible timeouts/retries, basic cost/usage tracking, admin health check |
| LIMIT-01 | P0 | Abuse protection | Per-IP/session/workspace rate and upload limits; concurrent call control; safe token and storage budgets |
| TEAM-01 | P1 | Membership UI | Invite members, Owner/Admin/Member role editing subject to permissions |
| AGT-02 | P1 | Multiple published agents | DB supports multiple now; management UI can follow pilot |
| BILL-01 | D | Billing | No subscriptions or paid plans in first MVP |
| OMNI-01 | D | Social channels | Facebook/Zalo after pilot |
| FLOW-01 | D | Workflow builder | No drag-and-drop UI in MVP |

## Fashion-specific response policy
- Suggest existing products with links and image cards; filter by category, generic options (including color/size where present), attributes, effective price and inventory state, with every option constraint matched by one actual variant.
- Size guidance must cite a shop size chart or explain it is only general guidance; ask clarifying questions for ambiguous fit.
- If stock is null/stale, say "chưa có thông tin tồn kho chính xác" instead of "còn hàng".
- If current price differs from an old retrieved document, current catalog record wins.
- Do not claim an order was placed or shipping date guaranteed; refer to documented shop policy and staff when uncertain.
- Visitor image matching is approximate and should be stated as such.

## MVP completion gate
A demo store can register, publish a website widget, import 20+ products with product-only and multi-option variant examples, ingest shop policy, chat with authoritative schema-neutral product cards and photo input, review consented leads, and pass isolation/security tests; real production readiness still requires a separately approved Docker-on-VPS phase, owner acceptance and operational checks.
