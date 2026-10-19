import type { WorkspaceOverview } from "@/lib/api";

export type WorldProjection = "system" | "agents";
export type SemanticLevel = "topology" | "structure" | "composition";
export type WorldNodeKind = "agent" | "knowledge" | "channel" | "catalog" | "location" | "collection" | "activity";
export type WorldNodeState = "normal" | "active" | "attention" | "error" | "paused" | "disabled";

export type WorldNode = {
  id: string;
  kind: WorldNodeKind;
  label: string;
  subtitle?: string;
  state: WorldNodeState;
  x: number;
  y: number;
  agentPublicId: string;
  route?: string;
};

export type WorldEdge = {
  id: string;
  source: string;
  target: string;
  kind: "structural" | "channel" | "runtime" | "attention";
};

export type WorldModel = {
  width: number;
  height: number;
  nodes: WorldNode[];
  edges: WorldEdge[];
};

const statusLabels = { draft: "Bản nháp", published: "Đã xuất bản", paused: "Tạm dừng" } as const;

function agentState(agent: WorkspaceOverview["agents"][number]): WorldNodeState {
  if (agent.lifecycle_state === "paused") return "paused";
  if (agent.attention_reasons.includes("knowledge_failed")) return "error";
  if (agent.attention_reasons.length) return "attention";
  return agent.lifecycle_state === "published" ? "active" : "normal";
}

function channelState(
  channel: WorkspaceOverview["agents"][number]["channels"]["web"]["items"][number],
): WorldNodeState {
  if (channel.lifecycle_state === "revoked" || !channel.enabled) return "disabled";
  if (!["unknown", "healthy"].includes(channel.health_state)) return "error";
  return "normal";
}

function addNode(nodes: WorldNode[], seen: Set<string>, node: WorldNode): void {
  if (seen.has(node.id)) return;
  seen.add(node.id);
  nodes.push(node);
}

export function buildWorldModel(
  overview: WorkspaceOverview,
  projection: WorldProjection,
  level: SemanticLevel,
): WorldModel {
  const nodes: WorldNode[] = [];
  const edges: WorldEdge[] = [];
  const seen = new Set<string>();
  const columns = overview.agents.length > 1 ? 2 : 1;
  const clusterWidth = 600;
  const clusterHeight = 370;

  overview.agents.forEach((agent, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const originX = 40 + column * clusterWidth;
    const originY = 40 + row * clusterHeight;
    const agentId = `agent:${agent.public_id}`;
    addNode(nodes, seen, {
      id: agentId,
      kind: "agent",
      label: agent.name,
      subtitle: statusLabels[agent.lifecycle_state],
      state: agentState(agent),
      x: originX + 300,
      y: originY + 170,
      agentPublicId: agent.public_id,
      route: `/app/${encodeURIComponent(overview.workspace_slug)}/chatbots?agent=${encodeURIComponent(agent.public_id)}`,
    });

    if (level === "topology") return;

    const channels = [
      ...agent.channels.web.items,
      ...agent.channels.facebook.items,
      ...agent.channels.zalo.items,
    ];
    channels.forEach((channel, channelIndex) => {
      const nodeId = `channel:${agent.public_id}:${channel.id}`;
      addNode(nodes, seen, {
        id: nodeId,
        kind: "channel",
        label: channel.display_name,
        subtitle: channel.provider === "web" ? "Website" : channel.provider === "facebook" ? "Facebook" : "Zalo",
        state: channelState(channel),
        x: originX + 45,
        y: originY + 85 + channelIndex * 86,
        agentPublicId: agent.public_id,
        route: `/app/${encodeURIComponent(overview.workspace_slug)}/chatbots?agent=${encodeURIComponent(agent.public_id)}&view=channels`,
      });
      edges.push({ id: `${nodeId}->${agentId}`, source: nodeId, target: agentId, kind: "channel" });
    });

    const showKnowledgeItems = projection === "agents" || level === "composition";
    if (showKnowledgeItems) {
      agent.knowledge.items.forEach((knowledge, knowledgeIndex) => {
        const nodeId = `knowledge:${agent.public_id}:${knowledge.id}`;
        addNode(nodes, seen, {
          id: nodeId,
          kind: "knowledge",
          label: knowledge.name,
          subtitle: "Kiến thức",
          state: knowledge.state === "failed" ? "error" : knowledge.state === "stale" ? "attention" : "normal",
          x: originX + 515,
          y: originY + 85 + knowledgeIndex * 74,
          agentPublicId: agent.public_id,
          route: `/app/${encodeURIComponent(overview.workspace_slug)}/knowledge`,
        });
        edges.push({ id: `${nodeId}->${agentId}`, source: nodeId, target: agentId, kind: knowledge.state === "ready" ? "structural" : "attention" });
      });
    } else if (agent.knowledge.total > 0) {
      const nodeId = `knowledge-group:${agent.public_id}`;
      addNode(nodes, seen, {
        id: nodeId,
        kind: "knowledge",
        label: "Kiến thức",
        subtitle: `${agent.knowledge.total} nguồn đã gán`,
        state: agent.attention_reasons.includes("knowledge_failed") ? "error" : agent.attention_reasons.includes("knowledge_stale") ? "attention" : "normal",
        x: originX + 515,
        y: originY + 145,
        agentPublicId: agent.public_id,
        route: `/app/${encodeURIComponent(overview.workspace_slug)}/knowledge`,
      });
      edges.push({ id: `${nodeId}->${agentId}`, source: nodeId, target: agentId, kind: "structural" });
    }

    if (agent.catalog_scope.available) {
      const catalogId = `catalog:${agent.public_id}`;
      addNode(nodes, seen, {
        id: catalogId,
        kind: "catalog",
        label: "Catalog scope",
        subtitle: `${agent.catalog_scope.collections.total} collection · ${agent.catalog_scope.locations.total} location`,
        state: "normal",
        x: originX + 300,
        y: originY + 330,
        agentPublicId: agent.public_id,
        route: `/app/${encodeURIComponent(overview.workspace_slug)}/catalog`,
      });
      edges.push({ id: `${agentId}->${catalogId}`, source: agentId, target: catalogId, kind: "structural" });
      if (level === "composition") {
        agent.catalog_scope.collections.items.slice(0, 4).forEach((collection, itemIndex) => {
          const nodeId = `collection:${agent.public_id}:${collection.id}`;
          addNode(nodes, seen, {
            id: nodeId,
            kind: "collection",
            label: collection.name,
            subtitle: "Collection",
            state: "normal",
            x: originX + 440 + itemIndex * 108,
            y: originY + 395,
            agentPublicId: agent.public_id,
            route: `/app/${encodeURIComponent(overview.workspace_slug)}/catalog/collections`,
          });
          edges.push({ id: `${catalogId}->${nodeId}`, source: catalogId, target: nodeId, kind: "structural" });
        });
        agent.catalog_scope.locations.items.slice(0, 4).forEach((location, itemIndex) => {
          const nodeId = `location:${agent.public_id}:${location.id}`;
          addNode(nodes, seen, {
            id: nodeId,
            kind: "location",
            label: location.name,
            subtitle: "Location",
            state: "normal",
            x: originX + 55 + itemIndex * 108,
            y: originY + 395,
            agentPublicId: agent.public_id,
            route: `/app/${encodeURIComponent(overview.workspace_slug)}/locations`,
          });
          edges.push({ id: `${catalogId}->${nodeId}`, source: catalogId, target: nodeId, kind: "structural" });
        });
      }
    }

    if (projection === "system") {
      const activityId = `activity:${agent.public_id}`;
      addNode(nodes, seen, {
        id: activityId,
        kind: "activity",
        label: `${agent.conversations.total} hội thoại`,
        subtitle: `${overview.days} ngày gần nhất`,
        state: agent.attention_reasons.includes("handover_pending") ? "attention" : "normal",
        x: originX + 300,
        y: originY + 30,
        agentPublicId: agent.public_id,
        route: `/app/${encodeURIComponent(overview.workspace_slug)}/conversations?agent=${encodeURIComponent(agent.public_id)}`,
      });
      edges.push({ id: `${agentId}->${activityId}`, source: agentId, target: activityId, kind: "runtime" });
    }
  });

  return {
    width: Math.max(760, Math.min(columns, Math.max(overview.agents.length, 1)) * clusterWidth + 80),
    height: Math.max(520, Math.ceil(Math.max(overview.agents.length, 1) / columns) * clusterHeight + 80),
    nodes,
    edges,
  };
}
