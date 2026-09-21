# Screens: authentication and first-run

## Routes and form content
`/register`: email, password, confirm password, consent/privacy links; show strength guidance without exposing raw password. `/login`: email/password, generic credential error, show password toggle accessible, rate-limit state. `/forgot-password` only when mail provider configured; otherwise do not expose a non-working route. `/onboarding/create-shop`: name, slug suggestion, optional shop homepage/brand; slug checked but auth confirmed server-side. Successful onboarding sends user to overview, then guided `Tạo chatbot` → `Thêm sản phẩm/tài liệu` → `Playground` → `Xuất bản` → `Lấy mã nhúng`.

## States/security UX
No user enumeration from forgot-password or login responses. UI should not claim email verification if no email channel is configured; for real deployment configure verification and recovery. Logout revokes refresh session then clears cookies; client clears shop-scoped cache. `Quên mật khẩu` failure keeps generic status to avoid account enumeration.

## Acceptance
Passwords never saved in localStorage; URLs do not contain access tokens; auth redirects safe (prevent open redirects); tab/keyboard interactions work; a user with zero shops lands onboarding; create shop gives owner membership atomically.
