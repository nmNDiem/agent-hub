# Agents

## Purpose

An agent combines behavior, allowed knowledge/catalog scope, tools and channel bindings. The fashion UI calls it a chatbot. Agent logic stays channel-neutral so one published agent can serve supported channels without duplicating reasoning.

## Current capability

- Workspace-owned drafts with name, greeting, locale and bounded safe instructions.
- Location/collection catalog scope and assigned knowledge bases.
- Authenticated Playground over the same grounded runtime used by the Website channel.
- Immutable published revision for the widget, publish/pause controls and Web branding/origin settings.
- Bounded OpenAI orchestration with validated product/source evidence.

## Complete domain capability

- Multiple managed agents per workspace and channel assignments.
- Draft/version history, comparison, rollback and controlled publishing.
- Tool allowlists, fallback/handoff policy and per-agent limits.
- Evaluation cases, human feedback, unresolved-question review and quality trends.
- Templates and reusable policies without copying tenant data.

## Lifecycle

`draft -> ready -> published -> paused -> archived`

Publishing creates an immutable snapshot. Later edits remain draft until republished. Pausing prevents new automated turns without deleting history. A channel connection may use only a compatible active published revision.

## Invariants

- Platform safety, tenancy and tool authorization are not editable agent instructions.
- Agent configuration never contains raw provider/channel secrets in public DTOs.
- Query intent can narrow assigned catalog/knowledge scope but cannot widen it.
- Product/source evidence is validated server-side before rendering.
- Model output cannot directly perform business writes; tools independently validate scope and policy.

Runtime mechanics are in [`../reference/agent-runtime.md`](../reference/agent-runtime.md).
