# 19 — Agent lifecycle, configuration and governance

## Entity/lifecycle
`draft -> ready -> published -> paused -> archived` with immutable published revision identifier. Validate minimum configuration, access to knowledge/catalog and enabled tools before publish. Pausing prevents new turns without erasing conversations. Agent deletion needs dependent channel/session/source semantics and audit trail.

## Configuration
Name, purpose, greeting, supported language(s), public identity, assistant policy, handoff instructions, website widget theme, knowledge-source bindings, model config reference, per-tool allowlist, rate and token ceilings, channel connection IDs. Never put OpenAI API key, internal prompts, tool secrets or private storage paths in public widget config.

## Prompt and tool boundaries
System rules and tenant policy originate on server, not from visitors/docs. Retrieved website content and shop documents are untrusted and quoted as data. Model output never directly changes data; only typed server tools may act after authz, scope and business-rule checks. Track tool IDs, confirmation, errors and selected source revisions with redaction.

## Evaluation before publish
Test effective product price/inventory retrieval, generic option/attribute filtering with same-variant semantics, product-only records, policy answer grounding, no-match handling, adversarial document prompts, cross-workspace data, cost ceilings, vision no-match and escalation. For a major prompt/model revision, run fixture regression and sample review before publishing.

## Future features
Agent templates (shop, portfolio, customer support), more than one concurrently published agent per workspace, channel-specific policy overrides, staged rollouts, experiment flags and workflow builder. Those are design targets, not MVP task authorization.
