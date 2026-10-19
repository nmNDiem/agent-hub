"use client";

import { BookOpen, Boxes, Focus, Globe2, ListTree, MapPin, MessageCircle, MessagesSquare, Minus, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

import type { WorkspaceOverview } from "@/lib/api";

import { buildWorldModel, type SemanticLevel, type WorldNode, type WorldProjection } from "./world-model";

type Camera = { x: number; y: number; zoom: number };
type OverviewAgent = WorkspaceOverview["agents"][number];
type RailResource = { id: number; name: string; agentIds: Set<string> };

function semanticLevel(zoom: number): SemanticLevel {
  if (zoom < 0.49) return "topology";
  if (zoom > 1.12) return "composition";
  return "structure";
}

function centerOf(node: WorldNode): { x: number; y: number } {
  return { x: node.x + 80, y: node.y + 31 };
}

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

function conversationRing(agent: OverviewAgent): CSSProperties {
  const total = Math.max(agent.conversations.total, 1);
  const human = Math.min(agent.conversations.human_handling, total);
  const pending = Math.min(agent.conversations.pending, Math.max(total - human, 0));
  const open = Math.min(agent.conversations.open, Math.max(total - human - pending, 0));
  const humanEnd = human / total * 100;
  const pendingEnd = humanEnd + pending / total * 100;
  const openEnd = pendingEnd + open / total * 100;
  return {
    background: `conic-gradient(#c62828 0 ${humanEnd}%, #e0a100 ${humanEnd}% ${pendingEnd}%, #3b4252 ${pendingEnd}% ${openEnd}%, #d7dbe2 ${openEnd}% 100%)`,
  };
}

function scopeLabel(scope: OverviewAgent["catalog_scope"]["collections"] | OverviewAgent["catalog_scope"]["locations"]): string {
  return scope.all_accessible ? "tất cả" : `${scope.total} đã chọn`;
}

function aggregateResources(agents: OverviewAgent[], kind: "collections" | "locations"): RailResource[] {
  const resources = new Map<number, RailResource>();
  agents.forEach((agent) => {
    agent.catalog_scope[kind].items.forEach((item) => {
      const existing = resources.get(item.id);
      if (existing) existing.agentIds.add(agent.public_id);
      else resources.set(item.id, { id: item.id, name: item.name, agentIds: new Set([agent.public_id]) });
    });
  });
  return [...resources.values()].sort((left, right) => left.name.localeCompare(right.name, "vi"));
}

function BusinessRail({ agents, activeAgentId, workspaceSlug }: {
  agents: OverviewAgent[];
  activeAgentId?: string;
  workspaceSlug: string;
}) {
  const collections = useMemo(() => aggregateResources(agents, "collections"), [agents]);
  const locations = useMemo(() => aggregateResources(agents, "locations"), [agents]);
  const relatedClass = (resource: RailResource): string => {
    if (!activeAgentId) return "";
    return resource.agentIds.has(activeAgentId) ? " is-related" : " is-muted";
  };
  const base = `/app/${encodeURIComponent(workspaceSlug)}`;

  return <aside aria-label="Dữ liệu kinh doanh" className="world-business-rail">
    <header>
      <p>Dữ liệu kinh doanh</p>
      <div><Boxes aria-hidden="true" size={18} /><span><strong>Catalog</strong><small>{agents.length} Agent đang dùng</small></span></div>
    </header>
    <section>
      <div className="world-rail-section-heading"><span>Bộ sưu tập</span><Link href={`${base}/catalog/collections`}>Quản lý</Link></div>
      {collections.length > 0 ? <ul>{collections.map((resource) => <li className={relatedClass(resource)} key={resource.id}>
        <span>{resource.name}</span><small>{resource.agentIds.size} Agent</small>
      </li>)}</ul> : <p className="world-rail-empty">Không có bộ sưu tập trong snapshot.</p>}
    </section>
    <section>
      <div className="world-rail-section-heading"><span>Địa điểm</span><Link href={`${base}/locations`}>Quản lý</Link></div>
      {locations.length > 0 ? <ul>{locations.map((resource) => <li className={relatedClass(resource)} key={resource.id}>
        <MapPin aria-hidden="true" size={13} /><span>{resource.name}</span><small>{resource.agentIds.size} Agent</small>
      </li>)}</ul> : <p className="world-rail-empty">Không có địa điểm trong snapshot.</p>}
    </section>
    <p className="world-rail-note">Rail chỉ phản ánh phạm vi Catalog đã được máy chủ cho phép.</p>
  </aside>;
}

function AgentUnit({ agent, modelNodes, projection, selectedId, level, dimmed, onHover, onSelect, onFocus }: {
  agent: OverviewAgent;
  modelNodes: WorldNode[];
  projection: WorldProjection;
  selectedId?: string;
  level: SemanticLevel;
  dimmed: boolean;
  onHover: (agentId?: string) => void;
  onSelect: (node: WorldNode) => void;
  onFocus: (node: WorldNode) => void;
}) {
  const agentNode = modelNodes.find((node) => node.id === `agent:${agent.public_id}`);
  if (!agentNode) return null;
  const relatedNodes = modelNodes.filter((node) => node.agentPublicId === agent.public_id && node.kind !== "agent");
  const channelNodes = relatedNodes.filter((node) => node.kind === "channel");
  const knowledgeNodes = relatedNodes.filter((node) => node.kind === "knowledge");
  const catalogNode = relatedNodes.find((node) => node.kind === "catalog");
  const hasAttention = agent.attention_reasons.length > 0;
  const unitStyle = { left: agentNode.x - 265, top: agentNode.y - 130 };
  const selectNode = (node: WorldNode | undefined) => onSelect(node ?? agentNode);

  return <article
    className={`world-agent-unit state-${agentNode.state}${dimmed ? " is-muted" : ""}`}
    onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) onHover(undefined); }}
    onFocus={() => onHover(agent.public_id)}
    onMouseEnter={() => onHover(agent.public_id)}
    onMouseLeave={() => onHover(undefined)}
    style={unitStyle}
  >
    <div className="world-channel-port" aria-label={`Kênh của ${agent.name}`}>
      {agent.channels.web.items.length + agent.channels.facebook.items.length + agent.channels.zalo.items.length === 0
        ? <button className="is-empty" onClick={() => onSelect(agentNode)} type="button">Chưa có kênh</button>
        : [...agent.channels.web.items, ...agent.channels.facebook.items, ...agent.channels.zalo.items].slice(0, 3).map((channel) => {
          const node = channelNodes.find((item) => item.id === `channel:${agent.public_id}:${channel.id}`);
          const failed = !channel.enabled || !["unknown", "healthy"].includes(channel.health_state);
          return <button
            aria-label={`${channel.display_name}${failed ? ", cần chú ý" : ""}`}
            className={failed ? "has-error" : ""}
            key={`${channel.provider}:${channel.id}`}
            onClick={() => selectNode(node)}
            type="button"
          >{channelIcon(channel.provider)}<span>{channel.display_name}</span></button>;
        })}
    </div>

    {level !== "topology" && <button
      className={`world-knowledge-bubble${agent.attention_reasons.some((reason) => reason.startsWith("knowledge_")) ? " has-error" : ""}`}
      onClick={() => selectNode(knowledgeNodes[0])}
      type="button"
    ><BookOpen aria-hidden="true" size={14} /><span>{agent.knowledge.total > 0 ? `${agent.knowledge.total} nguồn tri thức` : "Chưa có tri thức"}</span></button>}

    <button
      aria-label={`${agent.name}, ${lifecycleLabel(agent)}${hasAttention ? ", cần chú ý" : ""}`}
      aria-pressed={selectedId === agentNode.id}
      className="world-agent-core"
      onClick={() => onSelect(agentNode)}
      onDoubleClick={() => onFocus(agentNode)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          onFocus(agentNode);
          return;
        }
        if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) return;
        event.preventDefault();
        const cores = [...(event.currentTarget.closest(".world-plane")?.querySelectorAll<HTMLButtonElement>(".world-agent-core") ?? [])];
        const currentIndex = cores.indexOf(event.currentTarget);
        const direction = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
        cores[(currentIndex + direction + cores.length) % cores.length]?.focus();
      }}
      type="button"
    >
      <span className="world-conversation-ring" style={conversationRing(agent)}><span className="world-core-mark" /></span>
      <span className="world-agent-identity"><strong>{agent.name}</strong><small>{lifecycleLabel(agent)}</small>{hasAttention && <em>Cần chú ý</em>}</span>
    </button>

    {level !== "topology" && <div className="world-agent-activity" aria-label={`Hội thoại ${projection === "system" ? "trong kỳ" : ""}`}>
      <strong>{agent.conversations.total}</strong><span>hội thoại · {agent.conversations.pending} chờ · {agent.conversations.human_handling} cần người</span>
    </div>}

    {level === "composition" && projection === "agents" && agent.knowledge.items.length > 0 && <div className="world-knowledge-list">
      {agent.knowledge.items.slice(0, 3).map((knowledge) => <span key={knowledge.id}>{knowledge.name}</span>)}
    </div>}

    {level !== "topology" && <div className="world-agent-scope">
      {agent.catalog_scope.available ? <>
        <button onClick={() => selectNode(catalogNode)} type="button">Catalog · {scopeLabel(agent.catalog_scope.collections)} bộ sưu tập</button>
        <button onClick={() => selectNode(catalogNode)} type="button">{scopeLabel(agent.catalog_scope.locations)} địa điểm</button>
      </> : <span>Không dùng dữ liệu kinh doanh</span>}
    </div>}
  </article>;
}

export function WorldView({ overview, projection, selectedId, onSelect }: {
  overview: WorkspaceOverview;
  projection: WorldProjection;
  selectedId?: string;
  onSelect: (node?: WorldNode) => void;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<{ x: number; y: number; cameraX: number; cameraY: number } | undefined>(undefined);
  const [camera, setCamera] = useState<Camera>({ x: 20, y: 20, zoom: 1 });
  const [history, setHistory] = useState<Camera[]>([]);
  const [listMode, setListMode] = useState(false);
  const [hoveredAgentId, setHoveredAgentId] = useState<string>();
  const level = semanticLevel(camera.zoom);
  const model = useMemo(() => buildWorldModel(overview, projection, level), [level, overview, projection]);
  const selectedNode = model.nodes.find((node) => node.id === selectedId);
  const activeAgentId = hoveredAgentId ?? selectedNode?.agentPublicId;
  const catalogAgents = overview.agents.filter((agent) => agent.catalog_scope.available);

  const fitWorld = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const zoom = Math.max(0.48, Math.min(1, (viewport.clientWidth - 32) / model.width, (viewport.clientHeight - 32) / model.height));
    setCamera({ zoom, x: (viewport.clientWidth - model.width * zoom) / 2, y: Math.max(16, (viewport.clientHeight - model.height * zoom) / 2) });
  }, [model.height, model.width]);

  useEffect(() => { fitWorld(); }, [fitWorld, overview.workspace_id, projection]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const apply = () => setListMode(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (history.length) {
        const previous = history.at(-1);
        if (previous) setCamera(previous);
        setHistory((items) => items.slice(0, -1));
      } else onSelect(undefined);
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [history, onSelect]);

  function focusNode(node: WorldNode): void {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const nextZoom = Math.max(camera.zoom, 1.2);
    const center = centerOf(node);
    setHistory((items) => [...items.slice(-4), camera]);
    setCamera({ zoom: nextZoom, x: viewport.clientWidth / 2 - center.x * nextZoom, y: viewport.clientHeight / 2 - center.y * nextZoom });
    onSelect(node);
  }

  function zoomBy(delta: number): void {
    setCamera((current) => ({ ...current, zoom: Math.min(1.5, Math.max(0.48, current.zoom + delta)) }));
  }

  return <section className={`world-surface${catalogAgents.length > 0 ? " has-business-rail" : ""}${listMode ? " is-list" : ""}`} aria-label="Bản đồ workspace">
    <div className="world-toolbar">
      <span>{projection === "system" ? "Luồng vận hành" : "Phạm vi từng Agent"} · {level === "topology" ? "Tổng thể" : level === "structure" ? "Cấu trúc" : "Thành phần"}</span>
      <div>
        <button aria-label="Thu nhỏ" onClick={() => zoomBy(-0.12)} type="button"><Minus size={16} /></button>
        <button aria-label="Phóng to" onClick={() => zoomBy(0.12)} type="button"><Plus size={16} /></button>
        <button onClick={fitWorld} type="button"><Focus size={16} /> Vừa màn hình</button>
        <button aria-pressed={listMode} onClick={() => setListMode((value) => !value)} type="button"><ListTree size={16} /> Danh sách</button>
      </div>
    </div>
    <div className="world-stage">
      {listMode ? <div className="world-structured-view">
        {overview.agents.map((agent) => <article key={agent.public_id}>
          <button onClick={() => onSelect(model.nodes.find((node) => node.id === `agent:${agent.public_id}`))} type="button">
            <strong>{agent.name}</strong><span>{lifecycleLabel(agent)}</span>
          </button>
          <dl>
            <div><dt>Kiến thức</dt><dd>{agent.knowledge.total}</dd></div>
            <div><dt>Kênh</dt><dd>{agent.channels.web.total + agent.channels.facebook.total + agent.channels.zalo.total}</dd></div>
            <div><dt>Hội thoại</dt><dd>{agent.conversations.total}</dd></div>
            <div><dt>Cần chú ý</dt><dd>{agent.attention_reasons.length}</dd></div>
          </dl>
        </article>)}
      </div> : <div
        className="world-viewport"
        onPointerDown={(event) => {
          if (event.target instanceof Element && event.target.closest("button")) return;
          dragging.current = { x: event.clientX, y: event.clientY, cameraX: camera.x, cameraY: camera.y };
          event.currentTarget.classList.add("is-dragging");
          event.currentTarget.setPointerCapture(event.pointerId);
          onSelect(undefined);
        }}
        onPointerMove={(event) => {
          if (!dragging.current) return;
          setCamera((current) => ({ ...current, x: dragging.current!.cameraX + event.clientX - dragging.current!.x, y: dragging.current!.cameraY + event.clientY - dragging.current!.y }));
        }}
        onPointerCancel={(event) => { dragging.current = undefined; event.currentTarget.classList.remove("is-dragging"); }}
        onPointerUp={(event) => { dragging.current = undefined; event.currentTarget.classList.remove("is-dragging"); }}
        onWheel={(event) => {
          event.preventDefault();
          const viewport = viewportRef.current;
          if (!viewport) return;
          const bounds = viewport.getBoundingClientRect();
          const nextZoom = Math.min(1.5, Math.max(0.48, camera.zoom - event.deltaY * 0.001));
          const pointerX = event.clientX - bounds.left;
          const pointerY = event.clientY - bounds.top;
          const worldX = (pointerX - camera.x) / camera.zoom;
          const worldY = (pointerY - camera.y) / camera.zoom;
          setCamera({ zoom: nextZoom, x: pointerX - worldX * nextZoom, y: pointerY - worldY * nextZoom });
        }}
        ref={viewportRef}
      >
        <div className="world-plane" style={{ height: model.height, transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})`, width: model.width }}>
          {overview.agents.map((agent) => <AgentUnit
            agent={agent}
            dimmed={Boolean(activeAgentId && activeAgentId !== agent.public_id)}
            key={agent.public_id}
            level={level}
            modelNodes={model.nodes}
            onFocus={focusNode}
            onHover={setHoveredAgentId}
            onSelect={onSelect}
            projection={projection}
            selectedId={selectedId}
          />)}
        </div>
      </div>}
      {catalogAgents.length > 0 && !listMode && <BusinessRail activeAgentId={activeAgentId} agents={catalogAgents} workspaceSlug={overview.workspace_slug} />}
    </div>
  </section>;
}
