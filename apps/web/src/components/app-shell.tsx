"use client";

import {
  BarChart3,
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
import { useEffect, useState } from "react";

import { api, type CurrentUser, type Workspace, type WorkspaceOverview } from "@/lib/api";
import { PalettePicker } from "@/components/palette-picker";

const navigation: Array<{
  label: string;
  icon: typeof CircleGauge;
  segment: string;
  roles?: Workspace["role"][];
  capability?: "catalog";
}> = [
  { label: "World", icon: CircleGauge, segment: "overview" },
  { label: "Hội thoại", icon: MessageSquareText, segment: "conversations" },
  { label: "Liên hệ", icon: Users, segment: "contacts" },
  { label: "Agents", icon: Bot, segment: "chatbots" },
  { label: "Kiến thức", icon: BookOpen, segment: "knowledge" },
  { label: "Phân tích", icon: BarChart3, segment: "analytics", roles: ["owner", "admin"] },
  { label: "Catalog", icon: Boxes, segment: "catalog", capability: "catalog" },
  { label: "Locations", icon: MapPin, segment: "locations", capability: "catalog" },
  { label: "Collections", icon: Layers3, segment: "catalog/collections", capability: "catalog" },
];

function Navigation({
  workspace,
  catalogAvailable,
  capabilityStatusUnavailable,
}: {
  workspace: Workspace;
  catalogAvailable: boolean;
  capabilityStatusUnavailable: boolean;
}) {
  const pathname = usePathname();
  return (
    <>
      <nav aria-label="Điều hướng chính" className="navigation">
        {navigation.filter(({ roles, capability }) => (
          (!roles || roles.includes(workspace.role))
          && (!capability || catalogAvailable)
        )).map(({ label, icon: Icon, segment }) => {
          const href = `/app/${encodeURIComponent(workspace.slug)}/${segment}`;
          const active = pathname === href
            || (["chatbots", "knowledge", "conversations", "contacts"].includes(segment) && pathname.startsWith(`${href}/`));
          return (
            <Link aria-current={active ? "page" : undefined} className="nav-item" href={href} key={label}>
              <Icon aria-hidden="true" size={19} /><span>{label}</span>
            </Link>
          );
        })}
      </nav>
      {capabilityStatusUnavailable ? (
        <p className="navigation-state" role="status">Chưa thể xác định các khu vực tùy chọn.</p>
      ) : null}
    </>
  );
}

export function AppShell({
  children,
  user,
  workspaces,
  workspace,
  overview,
}: {
  children: ReactNode;
  user: CurrentUser;
  workspaces: Workspace[];
  workspace: Workspace;
  overview?: WorkspaceOverview | null;
}) {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [fetchedOverview, setFetchedOverview] = useState<{
    workspaceId: string;
    overview: WorkspaceOverview;
  }>();
  const [capabilityFailureWorkspaceId, setCapabilityFailureWorkspaceId] = useState<string>();

  useEffect(() => {
    if (overview !== undefined) return;
    let active = true;
    api.getWorkspaceOverview(workspace.id).then((result) => {
      if (active) {
        setFetchedOverview({ workspaceId: workspace.id, overview: result });
        setCapabilityFailureWorkspaceId(undefined);
      }
    }).catch(() => {
      if (active) setCapabilityFailureWorkspaceId(workspace.id);
    });
    return () => { active = false; };
  }, [overview, workspace.id]);

  const shellOverview = overview === undefined
    ? (fetchedOverview?.workspaceId === workspace.id ? fetchedOverview.overview : null)
    : overview;
  const catalogAvailable = shellOverview?.capabilities.catalog.available ?? false;
  const capabilityStatusUnavailable = overview === undefined
    && capabilityFailureWorkspaceId === workspace.id;

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
          <span><strong>AgentHub</strong><small>Không gian vận hành Agents</small></span>
        </Link>
        <Navigation
          capabilityStatusUnavailable={capabilityStatusUnavailable}
          catalogAvailable={catalogAvailable}
          workspace={workspace}
        />
        <div className="sidebar-footer"><Settings aria-hidden="true" size={19} /><span>Cài đặt</span><small>Sắp triển khai</small></div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <details className="mobile-navigation">
            <summary aria-label="Mở điều hướng"><Menu aria-hidden="true" size={22} /></summary>
            <div className="mobile-navigation-panel">
              <Navigation
                capabilityStatusUnavailable={capabilityStatusUnavailable}
                catalogAvailable={catalogAvailable}
                workspace={workspace}
              />
            </div>
          </details>
          <label className="workspace-switcher">
            <span className="sr-only">Chọn workspace</span>
            <span className="shop-icon" aria-hidden="true">{workspace.display_name.charAt(0).toUpperCase()}</span>
            <select
              aria-label="Chọn workspace"
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
