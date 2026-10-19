"use client";

import { Bot, Boxes, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { WorldInspector } from "@/features/world/world-inspector";
import { agentSelection, type WorldSelection } from "@/features/world/world-selection";
import { WorldView } from "@/features/world/world-view";
import { api, type WorkspaceOverview as WorkspaceOverviewData } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";
import { useWorkspaceSystem } from "@/lib/workspace-system-context";

export function WorkspaceOverview() {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const system = useWorkspaceSystem();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [requestedAgentId] = useState(() => searchParams.get("agent"));
  const [fallbackOverview, setFallbackOverview] = useState<WorkspaceOverviewData>();
  const [selectedNode, setSelectedNode] = useState<WorldSelection>();
  const [fallbackFeedback, setFallbackFeedback] = useState<UiFeedback>();
  const [fallbackLoading, setFallbackLoading] = useState(true);

  const loadFallback = useCallback(async (): Promise<void> => {
    if (!workspace || system) return;
    setFallbackLoading(true);
    try {
      setFallbackOverview(await api.getWorkspaceOverview(workspace.id, 7));
      setFallbackFeedback(undefined);
    } catch (caught) {
      setFallbackFeedback(toUiError(caught, {
        operation: "workspace.overview.load",
        fallback: "Không thể tải hệ thống của workspace. Hãy thử lại; dữ liệu hiện có không bị thay đổi.",
      }));
    } finally {
      setFallbackLoading(false);
    }
  }, [system, workspace]);

  useEffect(() => { void loadFallback(); }, [loadFallback]);

  const overview = system?.overview ?? fallbackOverview;
  const feedback = system?.overviewError ?? fallbackFeedback;
  const loading = system?.overviewLoading ?? fallbackLoading;
  const currentOverview = overview && workspace && overview.workspace_id === workspace.id && overview.days === 7
    ? overview
    : undefined;

  useEffect(() => {
    if (!currentOverview) return;
    setSelectedNode((current) => {
      if (current && currentOverview.agents.some((agent) => agent.public_id === current.agentPublicId)) return current;
      const requested = currentOverview.agents.find((agent) => agent.public_id === requestedAgentId);
      return requested ? agentSelection(currentOverview, requested) : undefined;
    });
  }, [currentOverview, requestedAgentId]);

  function updateLocation(nextSelected?: WorldSelection): void {
    if (!workspace) return;
    const query = new URLSearchParams();
    if (nextSelected?.kind === "agent") query.set("agent", nextSelected.agentPublicId);
    router.replace(`/app/${encodeURIComponent(workspace.slug)}/overview${query.size ? `?${query}` : ""}`, { scroll: false });
  }

  if (workspaceError) return <section className="centered-state"><FeedbackBanner feedback={workspaceError} /></section>;
  if (!me || !workspace) return <section className="centered-state"><LoaderCircle aria-hidden="true" className="spinner" /> Đang tải workspace…</section>;

  const degradedDependencies = currentOverview
    ? Object.entries(currentOverview.dependencies).filter(([, dependency]) => dependency.state !== "ready")
    : [];

  return <div className="world-screen">
    {currentOverview?.capabilities.catalog.can_setup && <div className="commerce-setup-callout"><div><Boxes aria-hidden="true" size={20} /><span><strong>Commerce là tùy chọn</strong><small>Thiết lập Catalog khi Agent cần dùng dữ liệu sản phẩm.</small></span></div><Link href={`/app/${encodeURIComponent(workspace.slug)}/catalog`}>Thiết lập Commerce</Link></div>}
    {degradedDependencies.length > 0 && <div className="world-partial-state" role="status"><TriangleAlert aria-hidden="true" size={18} /><span>Một phần hệ thống chưa đầy đủ: {degradedDependencies.map(([name]) => name).join(", ")}.</span></div>}

    {feedback && !currentOverview ? <section className="world-load-error"><FeedbackBanner feedback={feedback} /><button className="secondary-button" onClick={() => { if (system) void system.loadOverview(); else void loadFallback(); }} type="button"><RefreshCw size={16} /> Thử lại</button></section>
      : !currentOverview ? <section aria-live="polite" className="world-loading"><LoaderCircle aria-hidden="true" className="spinner" /><strong>Đang dựng hệ thống từ dữ liệu workspace…</strong><span>Agents, tri thức, kênh và hoạt động đang được tổng hợp.</span></section>
        : currentOverview.agents.length === 0 ? <section className="world-empty"><span><Bot aria-hidden="true" size={28} /></span><h2>Tạo Agent đầu tiên</h2><p>Agent là trung tâm kết nối tri thức, kênh và hội thoại trong workspace.</p><Link className="primary-button" href={`/app/${encodeURIComponent(workspace.slug)}/chatbots`}>Tạo Agent</Link></section>
          : <WorldView onSelect={(node) => { setSelectedNode(node); updateLocation(node); }} overview={currentOverview} selectedId={selectedNode?.id} />}

    {selectedNode && currentOverview && <><button aria-label="Đóng bảng chi tiết" className="world-inspector-scrim" onClick={() => { setSelectedNode(undefined); updateLocation(); }} type="button" /><WorldInspector node={selectedNode} onClose={() => { setSelectedNode(undefined); updateLocation(); }} overview={currentOverview} /></>}
    {currentOverview?.agents_truncated && <p className="world-truncated-note">Đang hiển thị 50/{currentOverview.agent_total} Agents. Mở màn hình Agents để quản lý toàn bộ.</p>}
    <span aria-live="polite" className="sr-only">{loading ? "Đang cập nhật hệ thống" : "Hệ thống đã cập nhật"}</span>
  </div>;
}
