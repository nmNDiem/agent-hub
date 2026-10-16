# Agents

## Function and ownership

An Agent is a workspace-owned operational actor: identity, instructions, assigned Knowledge, Conversations, Channels, allowed Actions/domain access, lifecycle state, published revision and handover relationships. It is generic even though the current runtime and UI retain Commerce-oriented fields and “Chatbot” wording.

## CURRENT

- Draft agents with name, greeting, locale, safe instructions, knowledge assignments, and catalog location/collection scope.
- Immutable published revisions, publish/pause/archive behavior, authenticated Playground, Website publication, and social-channel bindings.
- A bounded OpenAI runtime with knowledge retrieval and capability-aware typed Catalog read tools.
- Owner/admin Knowledge diagnostics may resolve an Agent's current Knowledge assignment server-side but do not call the chat model, create conversations, publish revisions or change bindings.
- Server-validated source/product evidence and usage accounting.

The runtime uses a generic base policy. It exposes Catalog tools and Catalog-specific instructions only when the Agent's server-authorized scope currently contains readable products; Knowledge-only Agents receive neither and cannot emit product cards.

Main data: agents, revisions, knowledge assignments, catalog scope joins and channel bindings. Main surfaces: Agent workbench, Playground and publish/channel configuration. Conversation/handover state remains owned by Conversations even when projected around an Agent.

## Core flow

Create identity → edit draft → assign Knowledge and current domain scope → test → validate referenced workspace resources → publish immutable revision → bind a supported Channel → receive a normalized message → compose server-owned policy and authorized read tools → persist response/evidence and usage → expose Conversation/handover state to operators.

## Invariants

- Instructions cannot override tenancy, safety, authorization, or provider policy.
- Query intent may narrow assigned scope but never widen it.
- Model output cannot directly write authoritative business state.
- Public DTOs never contain secrets; rendered evidence is revalidated server-side.
- Historical conversations keep their revision association.

## APPROVED DIRECTION

New Agent defaults and runtime composition no longer assume Commerce. Existing revisions remain compatible, while each execution derives Catalog availability from its server-authorized scope.

The Agent workspace should let an operator understand who the Agent is, what it knows, where it works, with whom it is speaking, what it may do, what it is doing, what it has done and when a person must intervene. Phase 3.2 projects real state into a multi-Agent World and coherent Create → Configure → Knowledge/access → Test → Publish → Observe → Improve path while preserving focused screens and accessible navigation.

Publish is not a decorative toggle. It selects an immutable executable revision. Readiness should be derived from real configuration—such as instructions, assigned Knowledge, valid Channel/provider state and future Action dependencies—and must distinguish blocking, optional, unavailable and unauthorized states. Full guided onboarding remains later work, but useful inline guidance is required earlier.

Before an effectful action exists, introduce a minimum typed action boundary: Agent → authorized action/tool → owning domain or external service → authoritative state, with typed input/output, validation, server-derived workspace and Agent permission, confirmation/approval where needed, idempotency, execution status, predictable errors, safe retries, attribution, durable redacted evidence and external-state reconciliation where applicable.

Evaluation suites, feedback, regression comparison and rollout evidence remain future phase 6.1 work. Quality tests specific to each new Agent capability remain part of that capability and are not deferred.

## NOT IMPLEMENTED

No generic plugin registry, workflow engine, arbitrary-code tools, general tool-call ledger, effectful Agent Action, autonomous payment/order/stock action or Agent-centric World implementation exists.

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
