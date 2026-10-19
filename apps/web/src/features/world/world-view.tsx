"use client";

import { ArrowRight, BookOpen, Boxes, Globe2, MapPin, MessageCircle, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

import type { WorkspaceOverview } from "@/lib/api";
import { AgentGlyph, agentGlyphColor } from "@/features/agents/agent-appearance";

import { agentSelection, relatedSelection, type WorldSelection, type WorldSelectionState } from "./world-selection";

type OverviewAgent = WorkspaceOverview["agents"][number];
type RailResource = { id: number; name: string; agentIds: Set<string> };

function lifecycleLabel(agent: OverviewAgent): string {
  if (agent.lifecycle_state === "published") return "Đã xuất bản";
  if (agent.lifecycle_state === "paused") return "Tạm dừng";
  return "Bản nháp";
}

function channelIcon(provider: "web" | "facebook" | "zalo"): ReactNode {
  if (provider === "web") return <Globe2 size={13} />;
  if (provider === "facebook") return <MessagesSquare size={13} />;
  return <MessageCircle size={13} />;
}

function channelLabel(provider: "web" | "facebook" | "zalo"): string {
  if (provider === "web") return "Website";
  if (provider === "facebook") return "Facebook";
  return "Zalo";
}

function channelState(channel: OverviewAgent["channels"]["web"]["items"][number]): WorldSelectionState {
  if (!channel.enabled || channel.lifecycle_state === "revoked") return "disabled";
  return ["unknown", "healthy"].includes(channel.health_state) ? "normal" : "error";
}

function conversationRing(agent: OverviewAgent): CSSProperties {
  const total = Math.max(agent.conversations.total, 1);
  const human = Math.min(agent.conversations.human_handling, total);
  const pending = Math.min(agent.conversations.pending, Math.max(total - human, 0));
  const open = Math.min(agent.conversations.open, Math.max(total - human - pending, 0));
  const humanEnd = human / total * 100;
  const pendingEnd = humanEnd + pending / total * 100;
  const openEnd = pendingEnd + open / total * 100;
  return { background: `conic-gradient(var(--world-human) 0 ${humanEnd}%, var(--world-waiting) ${humanEnd}% ${pendingEnd}%, var(--world-chat) ${pendingEnd}% ${openEnd}%, #d7dbe2 ${openEnd}% 100%)` };
}

function scopeLabel(scope: OverviewAgent["catalog_scope"]["collections"] | OverviewAgent["catalog_scope"]["locations"]): string {
  return scope.all_accessible ? "tất cả" : `${scope.total} đã chọn`;
}

function aggregateResources(agents: OverviewAgent[], kind: "collections" | "locations"): RailResource[] {
  const resources = new Map<number, RailResource>();
  agents.forEach((agent) => agent.catalog_scope[kind].items.forEach((item) => {
    const current = resources.get(item.id);
    if (current) current.agentIds.add(agent.public_id);
    else resources.set(item.id, { id: item.id, name: item.name, agentIds: new Set([agent.public_id]) });
  }));
  return [...resources.values()].sort((left, right) => left.name.localeCompare(right.name, "vi"));
}

function BusinessRail({ activeAgentId, agents, workspaceSlug }: {
  activeAgentId?: string;
  agents: OverviewAgent[];
  workspaceSlug: string;
}) {
  const collections = useMemo(() => aggregateResources(agents, "collections"), [agents]);
  const locations = useMemo(() => aggregateResources(agents, "locations"), [agents]);
  const base = `/app/${encodeURIComponent(workspaceSlug)}`;
  const relationClass = (item: RailResource): string => !activeAgentId
    ? ""
    : item.agentIds.has(activeAgentId) ? " is-related" : " is-muted";

  return <aside aria-label="Dữ liệu kinh doanh" className="world-business-rail">
    <header><p>Dữ liệu kinh doanh</p><div><Boxes aria-hidden="true" size={18} /><span><strong>Catalog</strong><small>{agents.length} Agent đang dùng</small></span></div></header>
    <section>
      <div className="world-rail-section-heading"><span>Bộ sưu tập</span><Link href={`${base}/catalog/collections`}>Quản lý</Link></div>
      {collections.length > 0 ? <ul>{collections.map((item) => <li className={relationClass(item)} key={item.id}><span>{item.name}</span><small>{item.agentIds.size} Agent</small></li>)}</ul> : <p className="world-rail-empty">Chưa có bộ sưu tập.</p>}
    </section>
    <section>
      <div className="world-rail-section-heading"><span>Địa điểm</span><Link href={`${base}/locations`}>Quản lý</Link></div>
      {locations.length > 0 ? <ul>{locations.map((item) => <li className={relationClass(item)} key={item.id}><MapPin aria-hidden="true" size={13} /><span>{item.name}</span><small>{item.agentIds.size} Agent</small></li>)}</ul> : <p className="world-rail-empty">Chưa có địa điểm.</p>}
    </section>
  </aside>;
}

function AgentUnit({ agent, onHover, onSelect, overview, selectedId }: {
  agent: OverviewAgent;
  onHover: (agentId?: string) => void;
  onSelect: (selection: WorldSelection) => void;
  overview: WorkspaceOverview;
  selectedId?: string;
}) {
  const primary = agentSelection(overview, agent);
  const channels = [...agent.channels.web.items, ...agent.channels.facebook.items, ...agent.channels.zalo.items];
  const knowledgeState: WorldSelectionState = agent.attention_reasons.includes("knowledge_failed")
    ? "error"
    : agent.attention_reasons.includes("knowledge_stale") ? "attention" : "normal";
  const knowledge = relatedSelection(agent, {
    id: `knowledge:${agent.public_id}`,
    kind: "knowledge",
    label: "Tri thức",
    subtitle: `${agent.knowledge.total} nguồn đã gán`,
    state: knowledgeState,
    route: `/app/${encodeURIComponent(overview.workspace_slug)}/knowledge`,
  });
  const catalog = relatedSelection(agent, {
    id: `catalog:${agent.public_id}`,
    kind: "catalog",
    label: "Catalog scope",
    subtitle: `${agent.catalog_scope.collections.total} bộ sưu tập · ${agent.catalog_scope.locations.total} địa điểm`,
    state: "normal",
    route: `/app/${encodeURIComponent(overview.workspace_slug)}/catalog`,
  });

  return <article
    className={`world-agent-unit state-${primary.state}`}
    onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) onHover(undefined); }}
    onFocus={() => onHover(agent.public_id)}
    onMouseEnter={() => onHover(agent.public_id)}
    onMouseLeave={() => onHover(undefined)}
  >
    <div className="world-channel-port" aria-label={`Kênh của ${agent.name}`}>
      {channels.length === 0 ? <span className="world-empty-port">Chưa có kênh</span> : channels.slice(0, 3).map((channel) => {
        const state = channelState(channel);
        const selection = relatedSelection(agent, {
          id: `channel:${agent.public_id}:${channel.id}`,
          kind: "channel",
          label: channel.display_name,
          subtitle: channel.provider === "web" ? "Website" : channel.provider === "facebook" ? "Facebook" : "Zalo",
          state,
          route: `/app/${encodeURIComponent(overview.workspace_slug)}/chatbots?agent=${encodeURIComponent(agent.public_id)}&view=channels`,
        });
        return <button aria-label={`${channelLabel(channel.provider)}: ${channel.display_name}`} className={state === "error" || state === "disabled" ? "has-error" : ""} key={`${channel.provider}:${channel.id}`} onClick={() => onSelect(selection)} title={channel.display_name} type="button">{channelIcon(channel.provider)}<span>{channel.display_name}</span></button>;
      })}
    </div>
    <button className={`world-knowledge-bubble state-${knowledge.state}`} onClick={() => onSelect(knowledge)} type="button"><BookOpen aria-hidden="true" size={14} /><span>{agent.knowledge.total > 0 ? `${agent.knowledge.total} nguồn` : "Chưa có tri thức"}</span></button>
    <button aria-label={`${agent.name}, ${lifecycleLabel(agent)}`} aria-pressed={selectedId === primary.id} className="world-agent-core" onClick={() => onSelect(primary)} type="button">
      <span className="world-conversation-ring" style={conversationRing(agent)}>
        <span
          className="world-core-mark"
          style={{ backgroundColor: agent.color, color: agentGlyphColor(agent.color) }}
        >
          <AgentGlyph icon={agent.icon} size={25} />
        </span>
      </span>
      <span className="world-agent-identity">
        <strong>{agent.name}</strong>
        <small>{lifecycleLabel(agent)}</small>
        <span className="world-agent-activity">
          <span className="world-agent-conversations">
            <span>{agent.conversations.total} hội thoại</span>
            <span aria-hidden="true">·</span>
            <span className={agent.conversations.pending > 0 ? "world-agent-waiting" : undefined}>{agent.conversations.pending} chờ</span>
          </span>
          {agent.conversations.human_handling > 0 && <em className="world-agent-handoff">{agent.conversations.human_handling} cần người</em>}
        </span>
      </span>
    </button>
    <div className="world-agent-scope">
      {agent.catalog_scope.available ? <><button onClick={() => onSelect(catalog)} type="button"><Boxes aria-hidden="true" size={12} />{scopeLabel(agent.catalog_scope.collections)} bộ sưu tập</button><button onClick={() => onSelect(catalog)} type="button"><MapPin aria-hidden="true" size={12} />{scopeLabel(agent.catalog_scope.locations)} địa điểm</button></> : <span>Không dùng dữ liệu kinh doanh</span>}
    </div>
  </article>;
}

export function WorldView({ onSelect, overview, selectedId }: {
  onSelect: (selection?: WorldSelection) => void;
  overview: WorkspaceOverview;
  selectedId?: string;
}) {
  const [hoveredAgentId, setHoveredAgentId] = useState<string>();
  const selectedAgentId = selectedId?.split(":")[1];
  const activeAgentId = hoveredAgentId ?? selectedAgentId;
  const catalogAgents = overview.agents.filter((agent) => agent.catalog_scope.available);

  return <section className={`system-world${catalogAgents.length > 0 ? " has-business-data" : ""}`} aria-label="Hệ thống workspace">
    <div className="world-agent-field">
      <div className="world-agent-grid">
        {overview.agents.map((agent) => <AgentUnit
          agent={agent}
          key={agent.public_id}
          onHover={setHoveredAgentId}
          onSelect={onSelect}
          overview={overview}
          selectedId={selectedId}
        />)}
      </div>
      <div aria-label="Chú thích hệ thống" className="world-legend" role="group">
        <span><i aria-hidden="true" className="world-legend-color is-chat" />Chat</span>
        <span><i aria-hidden="true" className="world-legend-color is-waiting" />Chờ</span>
        <span><i aria-hidden="true" className="world-legend-color is-human" />Cần người</span>
        <span className="world-legend-separator" aria-hidden="true" />
        <span><ArrowRight aria-hidden="true" size={15} />Kênh</span>
        <span><BookOpen aria-hidden="true" size={14} />Tri thức</span>
        <span><Boxes aria-hidden="true" size={14} />Phạm vi dữ liệu</span>
      </div>
    </div>
    {catalogAgents.length > 0 && <BusinessRail activeAgentId={activeAgentId} agents={catalogAgents} workspaceSlug={overview.workspace_slug} />}
  </section>;
}
