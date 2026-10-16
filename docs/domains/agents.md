# Agents

## Function and ownership

An Agent is a workspace-owned assistant configuration: identity, instructions, assigned knowledge, allowed capabilities, published revision, and channel bindings. It is generic even though the current runtime and UI retain Commerce-oriented fields.

## CURRENT

- Draft agents with name, greeting, locale, safe instructions, knowledge assignments, and catalog location/collection scope.
- Immutable published revisions, publish/pause/archive behavior, authenticated Playground, Website publication, and social-channel bindings.
- A bounded OpenAI runtime with knowledge retrieval and typed catalog read tools.
- Server-validated source/product evidence and usage accounting.

Main data: agents, revisions, knowledge assignments, catalog scope joins, and channel bindings. Main surfaces: agent workbench, Playground, and publish/channel configuration.

## Core flow

Edit draft → validate referenced workspace resources → publish immutable revision → bind a supported channel → receive a normalized message → compose server-owned policy and authorized read tools → persist response/evidence and usage.

## Invariants

- Instructions cannot override tenancy, safety, authorization, or provider policy.
- Query intent may narrow assigned scope but never widen it.
- Model output cannot directly write authoritative business state.
- Public DTOs never contain secrets; rendered evidence is revalidated server-side.
- Historical conversations keep their revision association.

## APPROVED DIRECTION

Remove mandatory Commerce assumptions from defaults and runtime composition while preserving existing revisions. Add evaluation cases, feedback, regression comparison, controlled rollout, and capability-aware onboarding.

Before an effectful action exists, introduce a minimum typed action boundary: Agent → authorized action/tool → owning domain service → authoritative PostgreSQL state, with validation, idempotency, approval policy, and durable redacted execution evidence.

## NOT IMPLEMENTED

No generic plugin registry, workflow engine, arbitrary-code tools, general tool-call ledger, or autonomous payment/order/stock action exists.

## Change trigger

The first approved non-read tool must define its concrete domain action and audit requirements; it must not cause a speculative universal framework.

## Dependencies and conditional references

- Knowledge assignments use [`knowledge.md`](knowledge.md); Catalog scope uses [`catalog.md`](catalog.md) only for Commerce-enabled behavior.
- Load [`../architecture.md#agent-runtime-boundary`](../architecture.md#agent-runtime-boundary) only for runtime composition/dependency changes.
- Load [`../security.md#ai-and-tools`](../security.md#ai-and-tools) only for tool authorization, side effects or model-trust changes.

## Relevant code paths

- `apps/api/src/agent_hub_api/agents/`
- `apps/web/src/features/agents/`
- `apps/widget/src/` and `apps/api/src/agent_hub_api/widget/` when publication/runtime behavior reaches Website visitors
