# 18 — Data governance, privacy and deletion

## Data categories
Account identity/password hashes/sessions; workspace/member records; product and public shop information; private knowledge documents; shopper messages/photos/contact information; token/cost metrics; connector credentials; audit events. Classify each data class at creation and avoid collecting unnecessary visitor details.

## Purposes and disclosure
Expose clear shop/operator privacy notices, consent for optional lead capture and transparent disclosure of AI use and any third-party processor relevant to the deployment. Do not silently send entire documents or personal profiles when small scoped snippets suffice. Validate applicable privacy requirements for actual deployment jurisdiction before going live; this document is a technical design, not legal advice.

## Retention policy
For the local pilot, visitor sessions and transcripts retain for 24 hours, unattached visitor images for 30 minutes, attached visitor images for one hour, and consented leads for 30 days. Image grants use their recorded expiry; obsolete widget rate windows are removed after two hours. The F5.3 one-shot sweeper processes bounded batches and is safe to rerun. It revokes sessions/conversations in Postgres before deleting content, clears private vision analysis before Storage cleanup, records a safe retry code when Storage deletion fails, and only purges parent tombstones after dependent records are gone. Usage facts contain no prompt/chat/image/PII content and remain after their nullable conversation link is cleared.

These are local-pilot defaults, not an approved production policy. Knowledge versions, account sessions, operational logs, failed processing files, usage/audit facts and backup expiry each still need separately approved production periods. Legal hold and jurisdiction-specific privacy wording remain open; validate them before going live.

## Erasure workflow
Verify requester and authorized workspace; record deletion request; immediately revoke retrievability in Postgres, then remove/soft-disable user-visible records and clean Qdrant points, Storage files and connector identifiers; propagate to future backups per feasible retention schedule; log the outcome without logging erased content. Handle dependent shared workspace/member records explicitly. Stale Qdrant points must not be usable because retrieval revalidates active Postgres generations. Provider retention cannot be assumed; verify current OpenAI, Qdrant hosting and Supabase terms/policies at deployment.

The operator command and restore/privacy checklist are documented in [`operations/local-pilot-runbook.md`](operations/local-pilot-runbook.md).

## Controls
Private buckets for shopper images and source files, narrowly scoped signed access URLs, content-type/signature validation, size caps, malware controls if appropriate, per-workspace encryption/permission boundaries, audit trail for privileged reads, redacted model traces, key rotation and session invalidation. Never place personal customer images in public sample datasets or analytics dashboards by default.
