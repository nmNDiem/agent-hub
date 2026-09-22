# Frontend architecture — Next.js

## Modules
`src/app/` contains App Router pages, layout and Next.js conventions. Domain UI lives in
`src/features/auth/` and `src/features/workspaces/`; route files stay thin and compose those feature
components. Reusable cross-feature UI stays in `src/components/`, while the API client and shared
utilities stay in `src/lib/`. The current authenticated flows call `/api/v1/me` through the shared
API client and redirect unauthenticated users to login. Runtime env is for public URLs only; secret
storage belongs on FastAPI/Next server, not in `NEXT_PUBLIC_*`.

Keep `apps/widget` independent from the dashboard application. Do not import dashboard features or
its React tree into the widget bundle.

## Rendering
Server Components for shell/session and non-interactive initial data where practical; client components for tables/filter/query, Playground stream, widget interactions and charts. The current auth and workspace feature components remain client components, preserving existing behavior. No `cache: force-cache` on user-specific API requests; use private/no-store for auth data. Avoid duplicate data fetching via inconsistent server-client query keys. Ensure streaming `fetch` isn't buffered by Next reverse proxy.

## Widget delivery
Small independent bundle on stable `/widget/v1/loader.js` route, ideally iframe with isolated styles, strict `postMessage` checks, CSP and responsive full-screen mobile. Do not import whole admin dashboard into widget; no duplicate React runtime if using a lightweight isolated launcher. Keep widget under performance budget, async script must not block host shop. Widget CSS/theme separate from admin tokens except component-level foundation.

## Frontend quality gates
TypeScript strict, ESLint, formatting, Vitest/RTL component tests. API type generation must fail CI on breaking contract drift.
