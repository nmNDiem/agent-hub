# Active task specifications

This directory contains only the task currently approved for implementation (or a very small set of explicitly concurrent approved tasks). Product scope belongs in [`../product.md`](../product.md), domain behavior in [`../domains/`](../domains/) and sequencing in [`../roadmap.md`](../roadmap.md).

Before implementation, create a concise functional context packet containing:

```text
Goal
User outcome
Relevant domain owner and current behavior
Acceptance criteria
Confirmed decisions
Data/API/UI/security impact
Test plan
Documentation impact
Out of scope
Compatibility/migration plan
Open decisions that block implementation
```

Link the task to one primary file under [`../domains/`](../domains/) and load other domain packets only for real dependencies. State which behavior is current, which change this task delivers, and which approved/future ideas remain unimplemented. A task must never rely on roadmap prose as an executable contract.

After completion, update the authoritative docs and remove the task file; Git preserves its history. Do not accumulate a second roadmap here.
