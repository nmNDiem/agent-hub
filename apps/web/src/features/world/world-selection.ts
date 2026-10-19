import type { WorkspaceOverview } from "@/lib/api";

export type WorldSelectionKind = "agent" | "knowledge" | "channel" | "catalog" | "location" | "collection" | "activity";
export type WorldSelectionState = "normal" | "active" | "attention" | "error" | "paused" | "disabled";

export type WorldSelection = {
  id: string;
  kind: WorldSelectionKind;
  label: string;
  subtitle?: string;
  state: WorldSelectionState;
  agentPublicId: string;
  route?: string;
};

type AgentSelectionSource = Pick<
  WorkspaceOverview["agents"][number],
  "attention_reasons" | "lifecycle_state" | "name" | "public_id"
>;

export function agentSelection(
  overview: Pick<WorkspaceOverview, "workspace_slug">,
  agent: AgentSelectionSource,
): WorldSelection {
  const state: WorldSelectionState = agent.lifecycle_state === "paused"
    ? "paused"
    : agent.attention_reasons.includes("knowledge_failed")
      ? "error"
      : agent.attention_reasons.length > 0
        ? "attention"
        : agent.lifecycle_state === "published" ? "active" : "normal";
  return {
    id: `agent:${agent.public_id}`,
    kind: "agent",
    label: agent.name,
    subtitle: agent.lifecycle_state === "published" ? "Đã xuất bản" : agent.lifecycle_state === "paused" ? "Tạm dừng" : "Bản nháp",
    state,
    agentPublicId: agent.public_id,
    route: `/app/${encodeURIComponent(overview.workspace_slug)}/chatbots?agent=${encodeURIComponent(agent.public_id)}`,
  };
}

export function relatedSelection(
  agent: Pick<WorkspaceOverview["agents"][number], "public_id">,
  values: Omit<WorldSelection, "agentPublicId">,
): WorldSelection {
  return { ...values, agentPublicId: agent.public_id };
}
