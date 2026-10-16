"use client";

import { Focus, ListTree, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { WorkspaceOverview } from "@/lib/api";

import { buildWorldModel, type SemanticLevel, type WorldNode, type WorldProjection } from "./world-model";

type Camera = { x: number; y: number; zoom: number };

function semanticLevel(zoom: number): SemanticLevel {
  if (zoom < 0.72) return "topology";
  if (zoom > 1.14) return "composition";
  return "structure";
}

function centerOf(node: WorldNode): { x: number; y: number } {
  return { x: node.x + (node.kind === "agent" ? 80 : 68), y: node.y + 31 };
}

function stateText(node: WorldNode): string | undefined {
  if (node.state === "attention") return "Cần chú ý";
  if (node.state === "error") return "Có lỗi";
  if (node.state === "paused") return "Tạm dừng";
  if (node.state === "disabled") return "Đã ngắt";
  return undefined;
}

export function WorldView({
  overview,
  projection,
  selectedId,
  onSelect,
}: {
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
  const level = semanticLevel(camera.zoom);
  const model = useMemo(
    () => buildWorldModel(overview, projection, level),
    [level, overview, projection],
  );

  const fitWorld = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const zoom = Math.max(
      0.48,
      Math.min(1, (viewport.clientWidth - 32) / model.width, (viewport.clientHeight - 32) / model.height),
    );
    setCamera({
      zoom,
      x: (viewport.clientWidth - model.width * zoom) / 2,
      y: Math.max(16, (viewport.clientHeight - model.height * zoom) / 2),
    });
  }, [model.height, model.width]);

  useEffect(() => {
    fitWorld();
  }, [fitWorld, overview.workspace_id, projection]);

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
      } else {
        onSelect(undefined);
      }
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
    setCamera({
      zoom: nextZoom,
      x: viewport.clientWidth / 2 - center.x * nextZoom,
      y: viewport.clientHeight / 2 - center.y * nextZoom,
    });
    onSelect(node);
  }

  function zoomBy(delta: number): void {
    setCamera((current) => ({ ...current, zoom: Math.min(1.5, Math.max(0.48, current.zoom + delta)) }));
  }

  function moveFocus(event: React.KeyboardEvent<HTMLButtonElement>, node: WorldNode): void {
    if (event.key === "Enter") {
      event.preventDefault();
      focusNode(node);
      return;
    }
    if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) return;
    event.preventDefault();
    const currentIndex = model.nodes.findIndex((item) => item.id === node.id);
    const direction = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
    const nextIndex = (currentIndex + direction + model.nodes.length) % model.nodes.length;
    viewportRef.current?.querySelector<HTMLButtonElement>(`[data-world-index="${nextIndex}"]`)?.focus();
  }

  return <section className="world-surface" aria-label="Bản đồ workspace">
    <div className="world-toolbar">
      <span>Mức chi tiết: {level === "topology" ? "Tổng thể" : level === "structure" ? "Cấu trúc" : "Thành phần"}</span>
      <div>
        <button aria-label="Thu nhỏ" onClick={() => zoomBy(-0.12)} type="button"><Minus size={16} /></button>
        <button aria-label="Phóng to" onClick={() => zoomBy(0.12)} type="button"><Plus size={16} /></button>
        <button onClick={fitWorld} type="button"><Focus size={16} /> Vừa màn hình</button>
        <button aria-pressed={listMode} onClick={() => setListMode((value) => !value)} type="button"><ListTree size={16} /> Danh sách</button>
      </div>
    </div>
    {listMode ? <div className="world-structured-view">
      {overview.agents.map((agent) => <article key={agent.public_id}>
        <button onClick={() => onSelect(model.nodes.find((node) => node.id === `agent:${agent.public_id}`))} type="button">
          <strong>{agent.name}</strong><span>{agent.lifecycle_state}</span>
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
        if (event.target instanceof Element && event.target.closest(".world-node")) return;
        dragging.current = { x: event.clientX, y: event.clientY, cameraX: camera.x, cameraY: camera.y };
        event.currentTarget.classList.add("is-dragging");
        event.currentTarget.setPointerCapture(event.pointerId);
        onSelect(undefined);
      }}
      onPointerMove={(event) => {
        if (!dragging.current) return;
        setCamera((current) => ({
          ...current,
          x: dragging.current!.cameraX + event.clientX - dragging.current!.x,
          y: dragging.current!.cameraY + event.clientY - dragging.current!.y,
        }));
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
        setCamera({
          zoom: nextZoom,
          x: pointerX - worldX * nextZoom,
          y: pointerY - worldY * nextZoom,
        });
      }}
      ref={viewportRef}
    >
      <div
        className="world-plane"
        style={{ height: model.height, transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})`, width: model.width }}
      >
        <svg aria-hidden="true" className="world-edges" height={model.height} width={model.width}>
          {model.edges.map((edge) => {
            const source = model.nodes.find((node) => node.id === edge.source);
            const target = model.nodes.find((node) => node.id === edge.target);
            if (!source || !target) return null;
            const from = centerOf(source);
            const to = centerOf(target);
            return <line className={`world-edge ${edge.kind}`} key={edge.id} x1={from.x} x2={to.x} y1={from.y} y2={to.y} />;
          })}
        </svg>
        {model.nodes.map((node, index) => <button
          aria-label={`${node.label}, ${node.subtitle ?? node.kind}${node.state !== "normal" ? `, trạng thái ${node.state}` : ""}`}
          aria-pressed={selectedId === node.id}
          className={`world-node ${node.kind} state-${node.state}`}
          data-world-index={index}
          key={node.id}
          onClick={(event) => { event.stopPropagation(); onSelect(node); }}
          onDoubleClick={() => focusNode(node)}
          onKeyDown={(event) => moveFocus(event, node)}
          style={{ left: node.x, top: node.y }}
          type="button"
        >
          <span className="world-node-symbol" aria-hidden="true" />
          <span><strong>{node.label}</strong>{node.subtitle && <small>{node.subtitle}</small>}{stateText(node) && <em>{stateText(node)}</em>}</span>
        </button>)}
      </div>
    </div>}
  </section>;
}
