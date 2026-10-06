# Reference image handoff

| File | Used for | Do not copy |
|---|---|---|
| `../../assets/reference/01-admin-dashboard.png` | Sidebar, typography, card composition, chart/table density, product thumbnails | Sample numbers, May 2025 dates, fake customer names, fake active Facebook/Zalo, copied UUID-like strings, Upgrade Plan before billing |
| `../../assets/reference/02-chatbot-playground.png` | Two-column layout, source/product card pattern, inputs | Screenshot's fixed GPT-4o picker, fabricated citation chips, unexplained model temperature knob, fashion product metadata |
| `../../assets/reference/03-website-chat-widget.png` | Widget size, avatar, quick prompts, product carousel, launcher | Shipping entire Lumé store, fake product pictures/prices, showing internal widget ID to shoppers, `Online` if unverified |
| `../../assets/reference/04-catalog-page.png` | Vietnamese admin density, compact sidebar, tables and detail hierarchy | Sample products, prices, counts, statuses or generated identities as live data |

Images are non-interactive **visual references** only; assets in mockups are not licenses to reuse pictures of people or merchandise as production inventory. When building a functional UI, recreate layout in HTML/CSS/shadcn, use seed data explicitly labelled for development and sourced from permitted images only. Actual shop products must come from shop DB/Storage. If visual and written rules conflict, written spec wins.

## Frontend handoff workflow
1. Attach all available reference images in coding agent context alongside docs.
2. Build AppShell, tokens and one empty-state page first; review at desktop 1440 and mobile 390.
3. Build reusable product/chat/status components; snapshot at 1440×900 and 390×844. Prefer correct layout and interactions over matching screenshot's pixel sizes.
4. Compare content density, spacing, alignment and responsive fallbacks; fix shared tokens, not screen-specific CSS hacks.
5. Run visual regression with baseline screenshots **from the coded UI**, not literal AI-generated pixels.

For any new screen or material redesign requested after the original handoff, create a visual mockup and obtain explicit owner approval before implementation. A mockup approves layout and interaction direction only: generated dates, identities, metrics, products, prices and statuses must never be copied as production facts. If implementation discovers an unplanned screen, stop at the design gate instead of improvising it in code.
