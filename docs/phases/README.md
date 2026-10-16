# Phase implementation packets

A phase packet is the single approved implementation contract between the roadmap and code. Do not add a separate task-planning layer.

Only a phase explicitly marked **Approved for implementation** and approved by the owner authorizes code changes. `Proposed` or `Next candidate` does not.

## Required structure

```markdown
# <phase ID> — <outcome>

Status
Goal
User-visible outcome

## Required Context
## Conditional Context
## Explicitly Unrelated
## Relevant Code Paths
## Existing Behavior to Preserve
## Scope
## Non-goals
## Confirmed Decisions
## Schema Impact
## API Impact
## Frontend Impact
## Security Impact
## Test Plan
## Documentation Impact
## Acceptance Criteria
## Blocking Owner Decisions
```

### Required Context

List the smallest documents that must be read before work—normally `AGENTS.md`, this phase packet and one or two primary domain packets.

### Conditional Context

For each optional reference, name the exact section and trigger. Do not list a document without saying when it becomes necessary.

### Explicitly Unrelated

Name tempting but unrelated material that should not be preloaded. Use this rule:

> Do not load unless code discovery proves a real dependency.

This is a context optimization, not a prohibition against following an actual dependency.

### Relevant Code Paths

List expected entry paths, not every file. The implementation still decides current truth.

## Material discovery notes

Use `docs/phases/context/<phase-id>.md` only when an implementation discovery would otherwise cause a later phase to repeat expensive investigation, choose a conflicting architecture, or miss a critical constraint. Do not record files opened, searches, line edits or routine progress. The approved phase packet remains the contract; discovery notes cannot expand scope.

After completion, update affected authoritative documents and keep the phase packet in Git as delivery history. Do not turn this directory into a second roadmap.
