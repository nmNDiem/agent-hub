# Frontend architecture — Next.js

## Modules
App Router route groups `(auth)` and `app/[shopSlug]`; server-side protected layout calls `/auth/me`, redirects unauthenticated to login. `src/lib/api` generated TS types from backend OpenAPI; hooks in feature modules; a per-shop query key prefix and cache invalidation on shop switch. Runtime env for public URLs only; secret storage on FastAPI/Next server, not `NEXT_PUBLIC_*`.

## Rendering
Server Components for shell/session and non-interactive initial data where practical; client components for tables/filter/query, Playground stream, widget interactions and charts. No `cache: force-cache` on user-specific API requests; use private/no-store for auth data. Avoid duplicate data fetching via inconsistent server-client query keys. Ensure streaming `fetch` isn't buffered by Next reverse proxy.

## Widget delivery
Small independent bundle on stable `/widget/v1/loader.js` route, ideally iframe with isolated styles, strict `postMessage` checks, CSP and responsive full-screen mobile. Do not import whole admin dashboard into widget; no duplicate React runtime if using a lightweight isolated launcher. Keep widget under performance budget, async script must not block host shop. Widget CSS/theme separate from admin tokens except component-level foundation.

## Frontend quality gates
TypeScript strict, ESLint, formatting, Vitest/RTL component tests, Playwright journey at 1440 and 390; axe or equivalent accessibility scan; visual snapshots checked after semantic behaviour. API type generation must fail CI on breaking contract drift.
