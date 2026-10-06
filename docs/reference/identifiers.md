# Identifier strategy

## Rule

Use UUIDv7 only where a stable opaque identifier is externally addressed or must be generated before persistence. Use BIGINT identity for dense internal rows. A PostgreSQL `uuid` column stores UUIDv7 values; there is no separate `uuidv7` SQL type.

| Entity | Primary/public identity |
|---|---|
| users | UUIDv7 primary key |
| workspaces | UUIDv7 primary key |
| agents | BIGINT primary key + globally unique UUIDv7 `public_id` |
| conversations | BIGINT primary key + globally unique UUIDv7 `public_id` |
| visitor image handles | UUIDv7 public handle where externally addressed |
| memberships, messages, products, variants, documents, chunks, jobs, events | BIGINT identity unless a documented external-addressing need is added |
| channel/provider IDs | Opaque provider strings namespaced by provider and connection |
| refresh/widget/session tokens | Cryptographically random bearer value stored only as a hash, never UUIDv7 |

## Generation

- Generate UUIDv7 server-side through the existing tested adapter; never silently fall back to UUIDv4.
- Do not require PostgreSQL native `uuidv7()` because the hosted PostgreSQL version may differ.
- API strings are lowercase, unprefixed, hyphenated UUIDs.
- UUIDs are identifiers, not secrets or authorization.
- Use `created_at` plus a deterministic tie-breaker for chronology; do not infer business time solely from UUIDv7 bits.
- Foreign key types must match their targets. Tenant-owned child relationships should use composite workspace-safe constraints where practical.

Mockup values such as `bot_...` are illustration labels and must not become canonical IDs or fixtures.
