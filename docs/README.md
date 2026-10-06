# AgentHub documentation

AgentHub is a multi-tenant, omnichannel AI-agent platform. F0-F5 are complete. The current delivery is M1 Omnichannel Operations: shared channel infrastructure, Facebook Messenger, Zalo, unified inbox, contacts and operational analytics.

## Canonical documents

| Question | Read |
|---|---|
| What product are we building? | [`product.md`](product.md) |
| What has the owner decided? | [`decisions.md`](decisions.md) |
| How is the system structured? | [`architecture.md`](architecture.md) |
| What entities and IDs exist? | [`data-model.md`](data-model.md) |
| What are the transport contracts? | [`api.md`](api.md) |
| What security rules are mandatory? | [`security.md`](security.md) |
| What is delivered next? | [`roadmap.md`](roadmap.md) |
| How does one business domain behave? | [`domains/`](domains/) |
| How should the interface behave? | [`ui.md`](ui.md) |
| How is quality verified? | [`testing.md`](testing.md) |
| How is the system run locally? | [`operations.md`](operations.md) |
| What task is currently approved? | [`tasks/`](tasks/) |

## Minimal reading routes

- Any task: `decisions.md`, `security.md` and the relevant domain file.
- Database/API work: additionally `data-model.md` or `api.md`.
- Frontend work: additionally `ui.md`.
- Verification/operations: additionally `testing.md` or `operations.md`.
- Product sequencing: `product.md` and `roadmap.md`.

Do not read every document by default. Historical specifications are available in Git history rather than duplicated in the working tree.

## Authority and vocabulary

Owner instructions and approved task acceptance criteria take precedence, followed by `decisions.md`, `security.md`, the relevant domain and the technical/UI document. Fix conflicts instead of silently choosing one.

`workspace` is the tenant and may be presented as a shop. `agent` is the domain entity and may be presented as a chatbot. Website, Facebook Messenger and Zalo are channel adapters over one conversation system.
