"use client";

import { ArrowRight, LockKeyhole, ShieldCheck, Store } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { api, ApiError, type Me, type Workspace } from "@/lib/api";

export function WorkspaceOverview() {
  const router = useRouter();
  const params = useParams<{ workspaceSlug: string }>();
  const [me, setMe] = useState<Me>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let active = true;
    api.getMe().then((data) => {
      if (!active) return;
      if (data.workspaces.length === 0) { router.replace("/onboarding/create-shop"); return; }
      const selected = data.workspaces.find((item) => item.slug === params.workspaceSlug);
      if (!selected) {
        setError("Không tìm thấy cửa hàng hoặc bạn không có quyền truy cập.");
        return;
      }
      setMe(data);
      setWorkspace(selected);
    }).catch((caught: unknown) => {
      if (!active) return;
      if (caught instanceof ApiError && caught.status === 401) router.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
      else setError("Không thể tải thông tin cửa hàng. Vui lòng thử lại.");
    });
    return () => { active = false; };
  }, [params.workspaceSlug, router]);

  if (error) return <main className="center-state"><p role="alert">{error}</p><button onClick={() => location.reload()}>Thử lại</button></main>;
  if (!me || !workspace) return <main className="center-state" aria-live="polite">Đang tải cửa hàng…</main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="page-heading">
        <div><p className="eyebrow">Không gian làm việc</p><h1>Tổng quan</h1><p>{workspace.display_name} đã sẵn sàng cho bước thiết lập tiếp theo.</p></div>
        <span className="role-badge"><ShieldCheck aria-hidden="true" size={15} /> {workspace.role}</span>
      </section>
      <section className="foundation-card">
        <div className="foundation-copy">
          <span className="feature-icon"><Store aria-hidden="true" size={24} /></span>
          <p className="eyebrow">Tenant đã được bảo vệ</p>
          <h2>Chưa có chatbot hoặc sản phẩm</h2>
          <p>Workspace này được tách biệt bằng membership phía server. Catalog và chatbot sẽ được mở ở các phase kế tiếp.</p>
          <Link href="#security">Xem nền tảng bảo mật <ArrowRight aria-hidden="true" size={17} /></Link>
        </div>
        <div className="foundation-visual" aria-hidden="true"><LockKeyhole size={74} /></div>
      </section>
      <section id="security" className="status-grid section-gap">
        <article className="status-card"><ShieldCheck aria-hidden="true" /><div><strong>Phân tách tenant</strong><small>Mọi API kiểm tra membership theo workspace.</small></div></article>
        <article className="status-card"><LockKeyhole aria-hidden="true" /><div><strong>Phiên bảo mật</strong><small>Cookie HttpOnly và refresh token xoay vòng.</small></div></article>
      </section>
    </AppShell>
  );
}
