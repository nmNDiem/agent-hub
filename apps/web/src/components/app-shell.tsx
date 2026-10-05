"use client";

import {
  Bot,
  BookOpen,
  Boxes,
  ChevronDown,
  CircleGauge,
  LogOut,
  Layers3,
  MapPin,
  Menu,
  MessageSquareText,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";

import { api, type CurrentUser, type Workspace } from "@/lib/api";
import { PalettePicker } from "@/components/palette-picker";

const navigation: Array<{
  label: string;
  icon: typeof CircleGauge;
  segment: string;
  enabled: boolean;
  roles?: Workspace["role"][];
}> = [
  { label: "Tổng quan", icon: CircleGauge, segment: "overview", enabled: true },
  { label: "Hội thoại", icon: MessageSquareText, segment: "conversations", enabled: true, roles: ["owner", "admin"] },
  { label: "Khách tiềm năng", icon: Users, segment: "leads", enabled: true, roles: ["owner", "admin"] },
  { label: "Chatbot", icon: Bot, segment: "chatbots", enabled: true },
  { label: "Catalog", icon: Boxes, segment: "catalog", enabled: true },
  { label: "Tri thức", icon: BookOpen, segment: "knowledge", enabled: true },
  { label: "Locations", icon: MapPin, segment: "locations", enabled: true },
  { label: "Collections", icon: Layers3, segment: "catalog/collections", enabled: true },
];

function Navigation({ workspace }: { workspace: Workspace }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Điều hướng chính" className="navigation">
      {navigation.filter(({ roles }) => !roles || roles.includes(workspace.role)).map(({ label, icon: Icon, segment, enabled }) => {
        const href = `/app/${encodeURIComponent(workspace.slug)}/${segment}`;
        const active = pathname === href
          || (["chatbots", "knowledge", "conversations"].includes(segment) && pathname.startsWith(`${href}/`));
        return enabled ? (
          <Link aria-current={active ? "page" : undefined} className="nav-item" href={href} key={label}>
            <Icon aria-hidden="true" size={19} /><span>{label}</span>
          </Link>
        ) : (
          <span className="nav-item" key={label}>
            <Icon aria-hidden="true" size={19} /><span>{label}</span><small>Sắp triển khai</small>
          </span>
        );
      })}
    </nav>
  );
}

export function AppShell({
  children,
  user,
  workspaces,
  workspace,
}: {
  children: ReactNode;
  user: CurrentUser;
  workspaces: Workspace[];
  workspace: Workspace;
}) {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function logout() {
    setLoggingOut(true);
    try { await api.logout(); } finally { router.replace("/login"); router.refresh(); }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Đi tới nội dung chính</a>
      <aside className="sidebar">
        <Link className="brand" href={`/app/${workspace.slug}/overview`}>
          <span className="brand-mark" aria-hidden="true"><Sparkles size={19} /></span>
          <span><strong>AgentHub</strong><small>AI cho cửa hàng thời trang</small></span>
        </Link>
        <Navigation workspace={workspace} />
        <div className="sidebar-footer"><Settings aria-hidden="true" size={19} /><span>Cài đặt</span><small>Sắp triển khai</small></div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <details className="mobile-navigation">
            <summary aria-label="Mở điều hướng"><Menu aria-hidden="true" size={22} /></summary>
            <div className="mobile-navigation-panel"><Navigation workspace={workspace} /></div>
          </details>
          <label className="workspace-switcher">
            <span className="sr-only">Chọn cửa hàng</span>
            <span className="shop-icon" aria-hidden="true">{workspace.display_name.charAt(0).toUpperCase()}</span>
            <select
              aria-label="Chọn cửa hàng"
              onChange={(event) => router.push(`/app/${encodeURIComponent(event.target.value)}/overview`)}
              value={workspace.slug}
            >
              {workspaces.map((item) => <option key={item.id} value={item.slug}>{item.display_name}</option>)}
            </select>
            <ChevronDown aria-hidden="true" size={17} />
          </label>
          <div className="account-menu">
            <span className="account-identity"><strong>{user.email}</strong><small>{workspace.role}</small></span>
            <PalettePicker />
            <button aria-label="Đăng xuất" disabled={loggingOut} onClick={logout} type="button"><LogOut aria-hidden="true" size={18} /></button>
          </div>
        </header>
        <main id="main-content" className="content">{children}</main>
      </div>
    </div>
  );
}
