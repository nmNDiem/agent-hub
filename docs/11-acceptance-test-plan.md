# 11 — Acceptance and regression checklist

Use this as manual and automated test source, not as a claim that tests currently exist.

## Owner onboarding
- [ ] User registers/logs in, verifies email, logs out and resets password securely.
- [ ] Owner creates shop workspace and cannot view a second workspace without membership.
- [ ] Owner creates agent, previews, allows shop origin and publishes website widget.

## Catalog and shop knowledge
- [ ] Products/variants imported through the same structure-driven pipeline from CSV/XLS/XLSX; invalid prices, duplicate SKU/option combinations and ambiguous identity are persisted and reported without partial catalog mutation.
- [ ] Import Analyze → Resolve → Diff does not mutate canonical rows; repeated Commit is idempotent, MERGE does not delete absent catalog records, and stale affected identities are revalidated.
- [ ] Generic options and attributes survive import/read/search; multiple option filters match one actual variant rather than different variants of the same product.
- [ ] Effective price comes from the current variant override or product fallback; unknown stock remains distinct from known zero and is never shown as available.
- [ ] Product images show only authorized and intended public files; remote references are not fetched by import analysis or commit.
- [ ] FAQ/PDF/TXT document ingestion reports pending/success/failed and preserves source reference.
- [ ] Updated documentation does not mix old/new versions in retrieval.

## Visitor
- [ ] Visitor can chat without account and receives streamed response/product cards.
- [ ] Can request arbitrary catalog options/attributes (including legacy size/color), stock and policy; uncertainty shown when data is missing.
- [ ] Can upload allowed clothing photo and receive clearly approximate catalog results.
- [ ] Can submit contact details only with explicit consent and see handoff CTA.
- [ ] Keyboard/mobile widget and host-page CSS isolation checked.

## Negative/security
- [ ] Workspace A cannot read/write B's products, documents, embeddings, leads or chat history.
- [ ] Workspace A cannot read/resolve/commit B's import jobs, issues, mapping profiles, external references or structured search results.
- [ ] Visitor session A cannot read visitor session B conversation.
- [ ] A malicious workspace ID in URL/body/tool args cannot change access scope.
- [ ] Unauthenticated user cannot get a signed URL for private doc/photo.
- [ ] No Supabase secret/service key, JWT signing secret or model key in widget bundle.
- [ ] Password hashed; reset tokens one-time; refresh rotation/replay checked.
- [ ] Oversized, forged MIME and corrupt uploads rejected.
- [ ] Prompt-injection in user-uploaded policy cannot invoke unauthorized tool or reveal data.
- [ ] Rate limit and exhausted model budget produce safe response.
- [ ] Logs and errors contain no secrets, unnecessary PII or raw sensitive images.

## Operational launch
- [ ] Tested migrations and rollback plan; staged/production separated.
- [ ] Database backup/restore and storage recovery documented.
- [ ] PII/image retention and user-facing privacy notice approved.
- [ ] Cost caps, upload limits, session expiry and allowed origins configured.
- [ ] Owner signs off on user-facing product/policy wording and contact destination.
