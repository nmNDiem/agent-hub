# Agents

## Function and ownership

An Agent is a workspace-owned operational actor: identity, instructions, assigned Knowledge, Conversations, Channels, allowed Actions/domain access, lifecycle state, published revision and handover relationships. It is generic even though the current runtime and UI retain Commerce-oriented fields and “Chatbot” wording.

## CURRENT

- Draft agents with name, greeting, locale, safe instructions, knowledge assignments, and catalog location/collection scope.
- Immutable published revisions, publish/pause/archive behavior, authenticated Playground, Website publication, and social-channel bindings.
- A bounded OpenAI runtime with knowledge retrieval and capability-aware typed Catalog read tools.
- An opt-in `contacts.follow_up.request` action for real published Website/Facebook/Zalo conversations. The permission is snapshotted into each immutable revision and rechecked on the live Agent so disable takes effect immediately; Playground never receives the effectful tool.
- One optional, bounded structured-intake definition and the `contacts.intake.submit` action. Server-generated field/option keys, purpose, disclosure version and enablement are snapshotted into the immutable revision; the live Agent can disable execution immediately and Playground never receives the tool.
- Owner/admin Knowledge diagnostics may resolve an Agent's current Knowledge assignment server-side but do not call the chat model, create conversations, publish revisions or change bindings.
- Server-validated source/product evidence and usage accounting.
- A bounded multi-Agent World projection with lifecycle, published revision, assigned Knowledge, Channel, Catalog scope, Conversation activity and safe attention summaries. The World links back to existing focused mutation surfaces.

The runtime uses a generic base policy. It exposes Catalog tools and Catalog-specific instructions only when the Agent's server-authorized scope currently contains readable products; Knowledge-only Agents receive neither and cannot emit product cards.

Main data: agents, revisions, knowledge assignments, catalog scope joins and channel bindings. Main surfaces: Agent workbench, Playground and publish/channel configuration. Conversation/handover state remains owned by Conversations even when projected around an Agent.

## Core flow

Create identity → edit draft → assign Knowledge and current domain scope → test → validate referenced workspace resources → publish immutable revision → bind a supported Channel → receive a normalized message → compose server-owned policy and authorized read tools → persist response/evidence and usage → expose Conversation/handover state to operators.

## Invariants

- Instructions cannot override tenancy, safety, authorization, or provider policy.
- Query intent may narrow assigned scope but never widen it.
- Model output cannot directly write authoritative business state.
- Customer-facing Agents communicate with the fluency, context awareness and initiative expected of capable staff without exposing internal schemas or forcing form-like turns. They never falsely claim to be human and identify themselves accurately when asked or when disclosure is required.
- Public DTOs never contain secrets; rendered evidence is revalidated server-side.
- Historical conversations keep their revision association.

## APPROVED DIRECTION

New Agent defaults and runtime composition no longer assume Commerce. Existing revisions remain compatible, while each execution derives Catalog availability from its server-authorized scope.

The Agent workspace should let an operator understand who the Agent is, what it knows, where it works, with whom it is speaking, what it may do, what it is doing, what it has done and when a person must intervene. Phase 3.2 projects real state into a multi-Agent World and coherent Create → Configure → Knowledge/access → Test → Publish → Observe → Improve path while preserving focused screens and accessible navigation.

Publish is not a decorative toggle. It selects an immutable executable revision. Readiness should be derived from real configuration—such as instructions, assigned Knowledge, valid Channel/provider state and future Action dependencies—and must distinguish blocking, optional, unavailable and unauthorized states. Full guided onboarding remains later work, but useful inline guidance is required earlier.

The first effectful action uses the minimum typed boundary: Agent → authorized action/tool → Contacts service → authoritative state. Runtime context supplies workspace, Agent, revision, Conversation, source message and Channel connection; model input is limited to bounded contact details and cannot grant permission or choose identity/provenance.

Structured intake preserves natural conversation as the customer interaction model. A customer answers in ordinary language; the Agent may interpret one reply into several typed proposed values, carries supported context forward, asks only for information that is missing or materially ambiguous, summarizes naturally and submits only after clear acceptance. Schemas, field keys and validation remain operator/backend concerns. It must not become a disguised step-by-step form, repeat questions for known information or fabricate a human identity. When ambiguity cannot be resolved safely, it leaves authoritative state unchanged and uses the existing human-handover path.

Evaluation suites, feedback, regression comparison and rollout evidence remain future phase 6.1 work. Quality tests specific to each new Agent capability remain part of that capability and are not deferred.

## NOT IMPLEMENTED

No generic plugin registry, workflow engine, arbitrary-code tools, general tool-call ledger or autonomous payment/order/stock action exists. The current World includes only the approved System/Agents slice; separate Catalog/Customer projections remain deferred.

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
