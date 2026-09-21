# 18 — Data governance, privacy and deletion

## Data categories
Account identity/password hashes/sessions; workspace/member records; product and public shop information; private knowledge documents; shopper messages/photos/contact information; token/cost metrics; connector credentials; audit events. Classify each data class at creation and avoid collecting unnecessary visitor details.

## Purposes and disclosure
Expose clear shop/operator privacy notices, consent for optional lead capture and transparent disclosure of AI use and any third-party processor relevant to the deployment. Do not silently send entire documents or personal profiles when small scoped snippets suffice. Validate applicable privacy requirements for actual deployment jurisdiction before going live; this document is a technical design, not legal advice.

## Retention proposal (durations OPEN)
Conversation text, uploaded photos, leads, knowledge versions, agent logs, failed processing files, sessions and audit events each need separately approved retention periods. Store created_at, deletion_due_at where appropriate, removal state and reason. Temporarily preserve data only for a documented purpose; define access to audit/legal-hold records if ever necessary.

## Erasure workflow
Verify requester and authorized workspace; record deletion request; remove/soft-disable user-visible records as appropriate; securely delete Storage files, embeddings, search indexes and connector identifiers; propagate to future backups per feasible retention schedule; log the outcome without logging erased content. Handle dependent shared workspace/member records explicitly. Provider retention cannot be assumed; verify current OpenAI and Supabase terms/policies at deployment.

## Controls
Private buckets for shopper images and source files, narrowly scoped signed access URLs, content-type/signature validation, size caps, malware controls if appropriate, per-workspace encryption/permission boundaries, audit trail for privileged reads, redacted model traces, key rotation and session invalidation. Never place personal customer images in public sample datasets or analytics dashboards by default.
