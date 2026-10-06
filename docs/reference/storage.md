# Storage and ingestion

## Storage policy

Customer/shop uploads, source documents, channel media and visitor photos use private Supabase Storage. Public buckets are only for deliberately published assets. Object keys are server-generated under workspace/resource namespaces; uploaded filenames are display metadata only.

Backend authorization precedes every signed URL or redirect. Service credentials never reach clients.

## Validation

- Stream through bounded buffers and reject overflow before completing upload.
- Validate declared MIME, magic bytes, decoded format, dimensions/pages and allowed extensions.
- Re-encode visitor images; reject malformed or unsupported content.
- Do not fetch arbitrary remote URLs. Provider media uses adapter-owned host allowlists and bounded fetch rules.
- Parse hostile documents outside the API process with time, CPU, memory and output limits; fail closed if isolation cannot be installed.

Current knowledge defaults: 10 MiB/document, 100 documents, 100 MiB source data/workspace, 10 uploads/10 minutes, 200 PDF pages, 1,000,000 extracted characters, 1,000 chunks/generation and 20,000 retained chunks/workspace. Stable defaults belong in typed config; deployment overrides must be explicit.

## Durable ingestion

`upload -> private asset/version -> persisted job -> isolated parse -> chunks -> batched embedding -> Qdrant upsert -> persisted index state -> atomic ready generation`

The worker claims PostgreSQL jobs with row locking, expiring lease, heartbeat and fencing token. External successes followed by database failure are replay-safe. Permanent invalid-content/config errors do not retry; transient provider/storage/network failures use bounded backoff.

Deletion/archive revokes the PostgreSQL active state first, cancels jobs and then cleans vectors/Storage asynchronously. Failed cleanup remains visible and retryable.
