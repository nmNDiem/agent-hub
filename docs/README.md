# AgentHub documentation

This directory is the current product and engineering authority. F0-F5 and M1 Omnichannel Operations are complete. M2 is next; no implementation task is active unless a specification exists under [`tasks/`](tasks/).

## Authority map

| Concept | Authoritative home |
|---|---|
| Product definition, users, scenarios and non-goals | [`product.md`](product.md) |
| Durable owner decisions | [`decisions.md`](decisions.md) |
| Topology, boundaries and dependency direction | [`architecture.md`](architecture.md) |
| Executable logical schema and clearly separated planned models | [`data-model.md`](data-model.md) |
| Mandatory security and privacy invariants | [`security.md`](security.md) |
| Delivery history, sequencing and phase design rules | [`roadmap.md`](roadmap.md) |
| API/event conventions and current route families | [`api.md`](api.md) |
| Product-wide UX principles | [`ui.md`](ui.md) |
| Detailed approved World UI direction | [`ui/README.md`](ui/README.md) |
| Current and planned behavior within one domain | [`domains/`](domains/) |
| Verification requirements | [`testing.md`](testing.md) |
| Setup and operations | [`operations.md`](operations.md) |
| Currently approved implementation scope | [`tasks/`](tasks/) |

Application models/migrations and generated OpenAPI are executable authority for current schema and transport details. Documentation defines ownership, invariants and approved direction; fix any discrepancy instead of silently treating planned behavior as implemented.

## Functional context packets

[`domains/`](domains/) is organized by business function rather than delivery phase or frontend page. Each file is a bounded context packet for an AI agent and follows the same shape:

1. **Function and ownership** — what the function owns and what it does not.
2. **CURRENT** — repository truth, including main data and UI/API surfaces.
3. **Core flow** — the shortest end-to-end execution path.
4. **Invariants** — rules that implementation must preserve.
5. **APPROVED DIRECTION** — accepted evolution constraints.
6. **NOT IMPLEMENTED** — explicit protection against treating plans as code.
7. **Change trigger** — evidence required before adding infrastructure or widening scope.
8. **Related authority** — only the cross-cutting documents needed for that function.

The packets are intentionally self-contained enough for focused work but do not duplicate field-level schema or route contracts. Inspect executable code whenever changing current behavior.

| Function | Context packet |
|---|---|
| Authentication and tenant authorization | [`domains/identity-workspaces.md`](domains/identity-workspaces.md) |
| Agent configuration, publishing and action boundary | [`domains/agents.md`](domains/agents.md) |
| Grounding and retrieval | [`domains/knowledge.md`](domains/knowledge.md) |
| External messaging adapters | [`domains/channels.md`](domains/channels.md) |
| Shared AI/human thread operations | [`domains/conversations.md`](domains/conversations.md) |
| Communication identity, consent and leads | [`domains/contacts.md`](domains/contacts.md) |
| Operational facts and quotas | [`domains/analytics.md`](domains/analytics.md) |
| Optional Commerce boundary | [`domains/commerce.md`](domains/commerce.md) |
| Product presentation | [`domains/catalog.md`](domains/catalog.md) |
| Stock truth and ledger trigger | [`domains/inventory.md`](domains/inventory.md) |
| AgentHub plans and subscriptions | [`domains/platform-billing.md`](domains/platform-billing.md) |

## Minimal reading routes

- Any implementation: this index, `AGENTS.md`, the active task, and the relevant functional packet. Follow that packet's related-authority links.
- Architecture or new domain: additionally `product.md` and `architecture.md`.
- Database: additionally `data-model.md` and the affected migrations/models.
- API/channel: additionally `api.md`.
- Frontend: additionally `ui.md`; World work also reads every file routed by `ui/README.md`.
- Verification/operations: additionally `testing.md` or `operations.md`.

Do not load or restate the entire documentation set in each task. Start from one function and expand context only across a real dependency boundary. Git history records completed task specifications and superseded detail; it is not current guidance.

## Vocabulary and status

- **CURRENT** means present in application code and migrations.
- **APPROVED DIRECTION** is a durable design constraint for future work.
- **PLANNED** is committed roadmap work that is not implemented.
- **FUTURE / UNSCHEDULED** is an allowed direction, not a commitment.
- **NON-GOAL** is explicitly excluded unless a new owner decision changes it.
- **TRIGGER** is the concrete event that justifies revisiting a decision or adding infrastructure.

`workspace` is the tenant, not a shop type. `agent` is the platform aggregate; current UI may call it a chatbot. Website, Facebook and Zalo are adapters over one channel/conversation model. Historical commerce-oriented names do not redefine these semantics.
