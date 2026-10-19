"use client";

import { BarChart3, BookOpen, Bot, Boxes, ChevronDown, ChevronLeft, Grid2X2, LogOut, MapPin, MessageSquareText, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { PalettePicker } from "@/components/palette-picker";
import { api, type CurrentUser, type Workspace, type WorkspaceOverview } from "@/lib/api";

type SystemLink = {
  href: string;
  icon: typeof Bot;
  label: string;
  roles?: Workspace["role"][];
  capability?: "catalog";
};

const focusLinks: Array<Omit<SystemLink, "href"> & { segment: string }> = [
  { label: "Agents", icon: Bot, segment: "chatbots" },
  { label: "Tri thức", icon: BookOpen, segment: "knowledge" },
  { label: "Liên hệ", icon: Users, segment: "contacts" },
  { label: "Phân tích", icon: BarChart3, segment: "analytics", roles: ["owner", "admin"] },
  { label: "Catalog", icon: Boxes, segment: "catalog", capability: "catalog" },
  { label: "Địa điểm", icon: MapPin, segment: "locations", capability: "catalog" },
  { label: "Bộ sưu tập", icon: Grid2X2, segment: "catalog/collections", capability: "catalog" },
];

function routeLabel(pathname: string): string {
  if (pathname.includes("/conversations")) return "Inbox";
  if (pathname.includes("/contacts")) return "Liên hệ";
  if (pathname.includes("/chatbots")) return "Agents";
  if (pathname.includes("/knowledge")) return "Tri thức";
  if (pathname.includes("/analytics")) return "Phân tích";
  if (pathname.includes("/locations")) return "Địa điểm";
  if (pathname.includes("/catalog/collections")) return "Bộ sưu tập";
  if (pathname.includes("/catalog")) return "Catalog";
  if (pathname.includes("/leads")) return "Khách tiềm năng";
  return "Không gian làm việc";
}

export function SystemShell({ children, overview, user, workspace, workspaces }: {
  children: React.ReactNode;
  overview?: Pick<WorkspaceOverview, "capabilities">;
  user: CurrentUser;
  workspace: Workspace;
  workspaces: Workspace[];
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const home = `/app/${encodeURIComponent(workspace.slug)}/overview`;
  const isSystemHome = pathname === home;
  const catalogAvailable = overview?.capabilities.catalog.available ?? false;
  const availableLinks = focusLinks.filter(({ roles, capability }) => (
    (!roles || roles.includes(workspace.role)) && (!capability || catalogAvailable)
  ));

  async function logout(): Promise<void> {
    setLoggingOut(true);
    try { await api.logout(); } finally { router.replace("/login"); router.refresh(); }
  }

  return <div className={`system-shell${isSystemHome ? " is-home" : " is-focused"}`}>
    <a className="skip-link" href="#main-content">Đi tới nội dung chính</a>
    <header className="system-header">
      <Link aria-label="Mở hệ thống workspace" className="system-brand" href={home}>
        <span className="system-brand-mark" aria-hidden="true">AH</span>
        <strong>AgentHub</strong>
      </Link>
      <label className="system-workspace-switcher">
        <span className="sr-only">Chọn workspace</span>
        <span aria-hidden="true">{workspace.display_name.charAt(0).toUpperCase()}</span>
        <select aria-label="Chọn workspace" onChange={(event) => router.push(`/app/${encodeURIComponent(event.target.value)}/overview`)} value={workspace.slug}>
          {workspaces.map((item) => <option key={item.id} value={item.slug}>{item.display_name}</option>)}
        </select>
        <ChevronDown aria-hidden="true" size={16} />
      </label>
      <nav aria-label="Điều hướng hệ thống" className="system-primary-nav">
        <Link aria-current={pathname.includes("/conversations") ? "page" : undefined} href={`/app/${encodeURIComponent(workspace.slug)}/conversations`}><MessageSquareText size={17} /> Inbox</Link>
        <details className="system-launcher">
          <summary><Grid2X2 aria-hidden="true" size={17} /> Điều hành</summary>
          <div className="system-launcher-panel">
            <header><strong>Mở vùng chuyên trách</strong><small>Dữ liệu và quyền vẫn thuộc domain sở hữu.</small></header>
            <div>{availableLinks.map(({ icon: Icon, label, segment }) => <Link href={`/app/${encodeURIComponent(workspace.slug)}/${segment}`} key={segment}><Icon aria-hidden="true" size={18} /><span>{label}</span></Link>)}</div>
            {!overview && <p>Đang xác định các vùng được phép truy cập…</p>}
          </div>
        </details>
      </nav>
      <div className="system-account">
        <span><strong>{user.email}</strong><small>{workspace.role}</small></span>
        <PalettePicker />
        <button aria-label="Đăng xuất" disabled={loggingOut} onClick={logout} type="button"><LogOut aria-hidden="true" size={18} /></button>
      </div>
    </header>
    {!isSystemHome && <div className="focus-context-bar">
      <Link href={home}><ChevronLeft aria-hidden="true" size={17} /> Hệ thống</Link>
      <span aria-hidden="true">/</span><strong>{routeLabel(pathname)}</strong>
    </div>}
    <main className="system-content" id="main-content">{children}</main>
  </div>;
}
