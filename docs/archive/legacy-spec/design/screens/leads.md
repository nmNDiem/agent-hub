# Screen: Consented leads

Route: `/app/[workspaceSlug]/leads`. The owner-approved F5.1 direction extends the compact catalog/admin shell; fictional values from reference images are never used as runtime data.

## Purpose and access

Show only visitor contact details created through explicit versioned widget consent. Owner and admin may list, update the small follow-up state and export CSV; member access is not represented as hidden authorization and remains denied by the API. This is a callback tracker, not a staffed inbox or CRM pipeline.

## Layout and behavior

Page heading explains the 30-day local-pilot retention. A bounded status filter (`Mới`, `Đã liên hệ`, `Đã hoàn tất`) drives server pagination. Rows show visitor-provided name/contact, chatbot, public conversation ID, captured time, retention deadline and one follow-up select. Loading, empty, error and forbidden states are explicit. On mobile the table may scroll horizontally without hiding its status action.

CSV export respects the active status filter, downloads only authorized workspace rows and preserves UTF-8 Vietnamese text. The backend neutralizes spreadsheet-formula prefixes; UI must not construct CSV from already rendered cells.

## Acceptance

No contact data appears before consent; no mock leads are shown. Workspace switching reloads scope. Updating status uses CSRF and reports mutation success independently of later refreshes. Dates use viewer locale with the exact ISO timestamp available as a tooltip.
