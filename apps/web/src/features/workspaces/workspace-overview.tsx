"use client";

import { Bot, Boxes, LoaderCircle, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { FeedbackBanner } from "@/components/feedback-banner";
import { WorldInspector } from "@/features/world/world-inspector";
import { buildWorldModel, type WorldNode, type WorldProjection } from "@/features/world/world-model";
import { WorldView } from "@/features/world/world-view";
import { api, type WorkspaceOverview as WorkspaceOverviewData } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

export function WorkspaceOverview() {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [days, setDays] = useState<7 | 30>(() => searchParams.get("days") === "30" ? 30 : 7);
  const [projection, setProjection] = useState<WorldProjection>(() => searchParams.get("projection") === "agents" ? "agents" : "system");
  const [requestedAgentId] = useState(() => searchParams.get("agent"));
  const [overview, setOverview] = useState<WorkspaceOverviewData>();
  const [selectedNode, setSelectedNode] = useState<WorldNode>();
  const [feedback, setFeedback] = useState<UiFeedback>();
  const [loading, setLoading] = useState(true);

  async function load(): Promise<void> {
    if (!workspace) return;
    try {
      const result = await api.getWorkspaceOverview(workspace.id, days);
      setOverview(result);
      setFeedback(undefined);
      setSelectedNode((current) => {
        if (current && result.agents.some((agent) => agent.public_id === current.agentPublicId)) return current;
        if (!requestedAgentId) return undefined;
        return buildWorldModel(result, "system", "structure").nodes.find(
          (node) => node.id === `agent:${requestedAgentId}`,
        );
      });
    } catch (caught) {
      setFeedback(toUiError(caught, {
        operation: "workspace.overview.load",
        fallback: "Không thể tải World của workspace. Hãy thử lại; dữ liệu hiện có không bị thay đổi.",
      }));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!workspace) return;
    let active = true;
    api.getWorkspaceOverview(workspace.id, days).then((result) => {
      if (!active) return;
      setOverview(result);
      setFeedback(undefined);
      setSelectedNode((current) => {
        if (current && result.agents.some((agent) => agent.public_id === current.agentPublicId)) return current;
        if (!requestedAgentId) return undefined;
        return buildWorldModel(result, "system", "structure").nodes.find(
          (node) => node.id === `agent:${requestedAgentId}`,
        );
      });
    }).catch((caught: unknown) => {
      if (!active) return;
      setFeedback(toUiError(caught, {
        operation: "workspace.overview.load",
        fallback: "Không thể tải World của workspace. Hãy thử lại; dữ liệu hiện có không bị thay đổi.",
      }));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [days, requestedAgentId, workspace]);

  function updateLocation(
    nextProjection: WorldProjection,
    nextDays = days,
    nextSelected = selectedNode,
  ): void {
    if (!workspace) return;
    const query = new URLSearchParams();
    if (nextProjection !== "system") query.set("projection", nextProjection);
    if (nextDays !== 7) query.set("days", String(nextDays));
    if (nextSelected?.kind === "agent") query.set("agent", nextSelected.agentPublicId);
    const suffix = query.size ? `?${query}` : "";
    router.replace(`/app/${encodeURIComponent(workspace.slug)}/overview${suffix}`, { scroll: false });
  }

  if (workspaceError) return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  if (!me || !workspace) return <main className="centered-state"><LoaderCircle className="spinner" aria-hidden="true" /> Đang tải workspace…</main>;

  const currentOverview = overview?.workspace_id === workspace.id ? overview : undefined;
  const degradedDependencies = currentOverview
    ? Object.entries(currentOverview.dependencies).filter(([, dependency]) => dependency.state !== "ready")
    : [];

  return <AppShell overview={currentOverview ?? null} user={me.user} workspace={workspace} workspaces={me.workspaces}>
    <div className="world-page-heading">
      <div>
        <p className="eyebrow"><Sparkles size={15} /> Workspace World</p>
        <h1>{workspace.display_name}</h1>
        <p>{projection === "system" ? "Workspace này được kết nối như thế nào?" : "Các Agent được cấu hình và phân phạm vi ra sao?"}</p>
      </div>
      <div className="world-heading-actions">
        <div className="world-projection-switch" aria-label="Projection" role="group">
          {(["system", "agents"] as const).map((value) => <button
            aria-pressed={projection === value}
            key={value}
            onClick={() => {
              const retainedNode = selectedNode?.kind === "agent" ? selectedNode : undefined;
              setProjection(value);
              setSelectedNode(retainedNode);
              updateLocation(value, days, retainedNode);
            }}
            type="button"
          >{value === "system" ? "Hệ thống" : "Agents"}</button>)}
        </div>
        <div className="period-switch" aria-label="Khoảng thời gian">
          {([7, 30] as const).map((value) => <button
            aria-pressed={days === value}
            key={value}
            onClick={() => { setLoading(true); setDays(value); updateLocation(projection, value); }}
            type="button"
          >{value} ngày</button>)}
        </div>
      </div>
    </div>

    {currentOverview?.capabilities.catalog.can_setup && <div className="commerce-setup-callout">
      <div><Boxes aria-hidden="true" size={20} /><span><strong>Commerce là tùy chọn</strong><small>Thiết lập Catalog khi Agent cần dùng dữ liệu sản phẩm.</small></span></div>
      <Link href={`/app/${encodeURIComponent(workspace.slug)}/catalog`}>Thiết lập Commerce</Link>
    </div>}

    {degradedDependencies.length > 0 && <div className="world-partial-state" role="status">
      <TriangleAlert aria-hidden="true" size={18} />
      <span>Một phần World chưa đầy đủ: {degradedDependencies.map(([name]) => name).join(", ")}.</span>
    </div>}

    {feedback && !currentOverview ? <section className="world-load-error">
      <FeedbackBanner feedback={feedback} />
      <button className="secondary-button" onClick={() => { setLoading(true); void load(); }} type="button"><RefreshCw size={16} /> Thử lại</button>
    </section> : !currentOverview ? <section className="world-loading" aria-live="polite">
      <LoaderCircle className="spinner" aria-hidden="true" />
      <strong>Đang dựng World từ dữ liệu workspace…</strong>
      <span>Agents, kiến thức, kênh và hoạt động đang được tổng hợp.</span>
    </section> : currentOverview.agents.length === 0 ? <section className="world-empty">
      <span><Bot aria-hidden="true" size={28} /></span>
      <h2>Tạo Agent đầu tiên</h2>
      <p>Agent là trung tâm kết nối kiến thức, kênh và hội thoại trong workspace.</p>
      <Link className="primary-button" href={`/app/${encodeURIComponent(workspace.slug)}/chatbots`}>Tạo Agent</Link>
    </section> : <div className={`world-workspace${selectedNode ? " has-inspector" : ""}`} aria-busy={loading}>
      <WorldView
        onSelect={(node) => { setSelectedNode(node); updateLocation(projection, days, node); }}
        overview={currentOverview}
        projection={projection}
        selectedId={selectedNode?.id}
      />
      <WorldInspector node={selectedNode} onClose={() => { setSelectedNode(undefined); updateLocation(projection, days, undefined); }} overview={currentOverview} />
    </div>}

    {currentOverview?.agents_truncated && <p className="world-truncated-note">Đang hiển thị 50/{currentOverview.agent_total} Agents. Mở màn hình Agents để quản lý toàn bộ.</p>}
  </AppShell>;
}
