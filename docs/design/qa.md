# Design QA / definition of done

## Universal
- [ ] Three reference images available at documented paths; shared shell visually consistent.
- [ ] Light theme default; dark theme either complete or control hidden; no half-themed dialogs.
- [ ] Real `vi-VN` copy; price/date/time based on data and locale; no demo facts in real UI.
- [ ] Responsive checks at 1440, 1024, 768, 390, 320 px; no horizontal overflow or hidden send button.
- [ ] Loading, empty, error, forbidden, long-content states tested for each async panel.
- [ ] Keyboard, focus return, screen-reader labels, visible focus, contrast and reduced motion reviewed.
- [ ] Shop switching clears stale scoped data; no access via direct route to other shop.
- [ ] Buttons reflect implemented operations; disabled future integrations never imply active connections.

## Dashboard
- [ ] KPI/data from correct shop; no generated values or unsupported deltas.
- [ ] Empty-first-run CTA; chart absent or true data; recent conversations paginate/link correctly.

## Playground
- [ ] Real streaming reply; stop/retry; real structured products/sources only.
- [ ] Draft vs published clearly marked; upload type/size errors and dirty-state warnings.

## Widget
- [ ] Can embed on separate static test page; host CSS isolation; focus/touch on small mobile.
- [ ] No OpenAI/API credentials/privileged IDs in JS; bot UUIDv7 exposed only as public identifier.
- [ ] Bot not published, invalid domain, rate limit, expired session and network failure handled visibly.

## Sign-off evidence
Include terminal logs for `lint`, `typecheck`, `test`, `build` (and backend pytest/migrations), screenshots 1440 and 390, actual API fixture payload for major components, security regression list and unimplemented feature list.
