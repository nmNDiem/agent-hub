"use client";

import { Eye, EyeOff, LoaderCircle, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { api, ApiError } from "@/lib/api";

type AuthMode = "login" | "register";
const PASSWORD_MIN_LENGTH = 8;

function safeDestination(value: string | null): string | null {
  return value && (value.startsWith("/app/") || value === "/onboarding/create-shop") ? value : null;
}

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    if (mode === "register" && password !== String(form.get("confirmPassword") ?? "")) {
      setError("Mật khẩu xác nhận chưa khớp.");
      return;
    }
    setPending(true);
    try {
      if (mode === "login") await api.login(email, password);
      else await api.register(email, password);
      const me = await api.getMe();
      const requested = safeDestination(searchParams.get("next"));
      const destination = requested ?? (me.workspaces[0]
        ? `/app/${encodeURIComponent(me.workspaces[0].slug)}/overview`
        : "/onboarding/create-shop");
      router.replace(destination);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Không thể kết nối máy chủ.");
    } finally {
      setPending(false);
    }
  }

  const isRegister = mode === "register";
  return (
    <main className="auth-page">
      <section className="auth-brand" aria-label="Giới thiệu AgentHub">
        <div className="brand-lockup">
          <span className="brand-mark"><Sparkles aria-hidden="true" size={24} /></span>
          <strong>AgentHub</strong>
        </div>
        <div>
          <p className="eyebrow">AI cho cửa hàng thời trang</p>
          <h1>Quản lý trợ lý bán hàng từ một nơi duy nhất.</h1>
          <p>Tạo không gian riêng cho shop, bảo vệ dữ liệu theo từng tenant và sẵn sàng mở rộng.</p>
        </div>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <div>
            <p className="eyebrow">{isRegister ? "Bắt đầu" : "Chào mừng trở lại"}</p>
            <h2>{isRegister ? "Tạo tài khoản" : "Đăng nhập AgentHub"}</h2>
            <p>{isRegister ? "Thiết lập tài khoản chủ shop của bạn." : "Tiếp tục quản lý cửa hàng của bạn."}</p>
          </div>
          <label htmlFor={`${mode}-email`}>
            Email
            <input autoComplete="email" id={`${mode}-email`} name="email" required type="email" />
          </label>
          <label htmlFor={`${mode}-password`}>
            Mật khẩu
            <span className="password-field">
              <input
                autoComplete={isRegister ? "new-password" : "current-password"}
                id={`${mode}-password`}
                minLength={isRegister ? PASSWORD_MIN_LENGTH : 1}
                name="password"
                required
                type={showPassword ? "text" : "password"}
              />
              <button aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"} onClick={() => setShowPassword((value) => !value)} type="button">
                {showPassword ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
              </button>
            </span>
            {isRegister && <small>Tối thiểu 8 ký tự, gồm ít nhất một chữ và một số.</small>}
          </label>
          {isRegister && (
            <label htmlFor="confirm-password">
              Xác nhận mật khẩu
              <input autoComplete="new-password" id="confirm-password" minLength={PASSWORD_MIN_LENGTH} name="confirmPassword" required type="password" />
            </label>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={pending} type="submit">
            {pending && <LoaderCircle className="spinner" aria-hidden="true" size={18} />}
            {pending ? "Đang xử lý…" : isRegister ? "Tạo tài khoản" : "Đăng nhập"}
          </button>
          <p className="auth-switch">
            {isRegister ? "Đã có tài khoản?" : "Chưa có tài khoản?"}{" "}
            <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Đăng nhập" : "Đăng ký"}</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
