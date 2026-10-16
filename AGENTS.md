# AgentHub — coding-agent contract

AgentHub is a general-purpose AI Agent platform. Workspace is a generic tenant boundary, Agent is a generic configurable aggregate, and Commerce is an optional first substantial domain capability. Platform/Core must work without Commerce.

## Working protocol

1. Locate the active approved packet under [`docs/phases/`](docs/phases/).
2. Read its **Required Context** only; do not preload unrelated documentation for completeness.
3. Inspect the relevant implementation and treat working code/migrations as current truth unless the approved requirement changes it.
4. Load a **Conditional Context** reference only when its stated trigger applies or code discovery proves a real dependency.
5. Report conflicts between the phase, implementation, durable decisions and security constraints before changing architecture.
6. Present a plan and obtain approval before non-trivial implementation; obtain UI direction approval before a new or materially redesigned screen.

If no phase is explicitly approved, do not infer implementation authority from the roadmap.

## Permanent rules

- Domain modules own authoritative state. Agents access domain behavior through authorized typed tools/actions and domain services; model output never directly mutates authoritative data.
- PostgreSQL is authoritative relational state. Qdrant is a derived, filtered and rebuildable index. The LLM is a runtime, never a source of truth.
- Keep price, SKU, inventory, order and payment state in structured owning domains, not RAG, prompts or Agent configuration.
- Preserve the modular monolith and `router/adapter -> service/use case -> repository/provider` direction. Services own authorization, rules and transactions; repositories do not commit independently.
- Scope every tenant-owned operation, join, job, vector search, Storage object and tool call to validated server-side workspace context. Never trust client/provider identity or permission claims.
- Treat prompts, documents, uploads, provider payloads and model/tool output as untrusted. Keep secrets, private content and PII out of public responses, browser bundles and logs.
- Preserve working APIs, identifiers and behavior unless a breaking change is explicitly approved. Migrations must solve a concrete requirement.
- Do not add speculative plugin/capability registries, workflow engines, unused provider abstractions, one Agent model per use case, or one microservice per domain.
- Do not refactor or rename working code for conceptual purity. Do not implement future phases opportunistically.
- Before effectful tools or external side effects, define authorization, idempotency, audit/attribution, failure behavior and approval policy where required.

Do not replace the approved stack without an architecture decision. Use Alembic for schema changes, add tenant-isolation coverage for exposed tenant resources, avoid paid provider calls in automated tests, update the single authoritative document, report exact verification, and create a focused Conventional Commit after completion.
