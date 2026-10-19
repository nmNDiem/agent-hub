"use client";

import { ArrowRight, BookOpen, Boxes, MessageSquareText, Radio, TestTube2, X } from "lucide-react";
import Link from "next/link";

import type { OverviewAttentionReason, WorkspaceOverview } from "@/lib/api";
import type { WorldSelection } from "./world-selection";

const attentionLabels: Record<OverviewAttentionReason, string> = {
  knowledge_stale: "Có kiến thức cần rà soát",
  knowledge_failed: "Có nguồn kiến thức xử lý thất bại",
  website_not_ready: "Website chưa đủ điều kiện xuất bản",
  channel_disconnected: "Có kênh đã ngắt kết nối",
  channel_degraded: "Có kênh đang suy giảm",
  handover_pending: "Có hội thoại cần con người xử lý",
};

export function WorldInspector({
  node,
  overview,
  onClose,
}: {
  node?: WorldSelection;
  overview: WorkspaceOverview;
  onClose: () => void;
}) {
  if (!node) return null;
  const agent = overview.agents.find((item) => item.public_id === node.agentPublicId);
  if (!agent) return null;
  const base = `/app/${encodeURIComponent(overview.workspace_slug)}`;

  return <aside aria-label={`Chi tiết ${node.label}`} className="world-inspector">
    <header>
      <div><p>{node.kind === "agent" ? "Agent" : node.subtitle ?? node.kind}</p><h2>{node.label}</h2></div>
      <button aria-label="Đóng bảng chi tiết" onClick={onClose} type="button"><X size={18} /></button>
    </header>
    {node.kind === "agent" && <>
      {agent.attention_reasons.length > 0 && <section className="inspector-attention">
        <h3>Cần chú ý</h3>
        <ul>{agent.attention_reasons.map((reason) => <li key={reason}>{attentionLabels[reason]}</li>)}</ul>
      </section>}
      <section>
        <h3>Hoạt động {overview.days} ngày</h3>
        <dl className="inspector-facts">
          <div><dt>Đang mở</dt><dd>{agent.conversations.open}</dd></div>
          <div><dt>Đang chờ</dt><dd>{agent.conversations.pending}</dd></div>
          <div><dt>Con người xử lý</dt><dd>{agent.conversations.human_handling}</dd></div>
        </dl>
      </section>
      <section>
        <h3>Tiếp tục vòng đời Agent</h3>
        <nav className="inspector-actions" aria-label="Thao tác Agent">
          <Link href={`${base}/chatbots?agent=${agent.public_id}`}><Radio size={16} /> Cấu hình Agent <ArrowRight size={15} /></Link>
          <Link href={`${base}/knowledge`}><BookOpen size={16} /> Quản lý kiến thức <ArrowRight size={15} /></Link>
          <Link href={`${base}/chatbots/${agent.public_id}/playground`}><TestTube2 size={16} /> Kiểm thử <ArrowRight size={15} /></Link>
          <Link href={`${base}/chatbots?agent=${agent.public_id}&view=channels`}><Radio size={16} /> Xuất bản và kênh <ArrowRight size={15} /></Link>
          <Link href={`${base}/conversations?agent=${agent.public_id}`}><MessageSquareText size={16} /> Xem hội thoại <ArrowRight size={15} /></Link>
          {agent.catalog_scope.available && <Link href={`${base}/catalog`}><Boxes size={16} /> Quản lý Catalog <ArrowRight size={15} /></Link>}
        </nav>
      </section>
    </>}
    {node.kind !== "agent" && <section>
      <p className="inspector-copy">Thành phần này thuộc phạm vi của <strong>{agent.name}</strong>. Mở màn hình chuyên trách để xem hoặc thay đổi dữ liệu.</p>
      {node.route && <Link className="inspector-primary-link" href={node.route}>Mở màn hình quản lý <ArrowRight size={16} /></Link>}
    </section>}
  </aside>;
}
