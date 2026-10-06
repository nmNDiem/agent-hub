# 15 — SaaS, roles, usage and future billing

## Tenant model
User ↔ workspace membership (many-to-many); workspace owns agents, channel connections, catalog, sources, contacts, conversations, usage and policies. Initial owner-only UI must not block future multiple members and multiple agents. Keep roles explicit and check on the server per action; UI visibility is not authorization.

## Proposed RBAC (subject to owner approval before launch)
| Operation | Owner | Admin | Member |
|---|---|---|---|
| Workspace deletion/plan/billing | Yes | No | No |
| Invite/remove members | Yes | Yes (not owner) | No |
| Configure/publish agents and channels | Yes | Yes | Read/limited |
| Catalog/knowledge edits | Yes | Yes | Permission-scoped |
| Conversations/leads | Yes | Yes | Assigned/permission-scoped |
| Platform support bypass | No | No | No |

## MVP usage requirements
Capture workspace_id, agent_id, conversation_id, model ID, token/usage counters when returned, estimated provider cost, image/embedding/storage counts and throttling outcomes. Do not assume model/token price is constant; prices and categories are configurable. Apply server-side hard cap/rate limit independent of UI; fail safely, never continue unlimited OpenAI calls.

## Future billing domain
Plans define entitlements; subscriptions track provider state; ledger tracks immutable usage events and credits; invoices/payment events are reconciled idempotently. Webhook processing validates signatures, ignores duplicates, records disputes/cancellations, and gates entitlement on documented state rules. Avoid handling card numbers directly. No live billing until a separately approved design and security test.

## Future workspace lifecycle
Trial -> active -> restricted -> suspended -> scheduled deletion -> erased, with billing, appeals and data-export policies explicitly specified. On suspension, stop new model spend; allow permissible exports and account access. Tenant deletion must handle DB rows, Storage objects, vector embeddings, channel tokens and backups under an approved retention policy.
