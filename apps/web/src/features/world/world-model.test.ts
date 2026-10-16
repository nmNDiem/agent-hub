import { describe, expect, it } from "vitest";

import type { WorkspaceOverview } from "@/lib/api";

import { buildWorldModel } from "./world-model";

const overview = {
  workspace_slug: "example",
  days: 7,
  agents: [{
    public_id: "agent-1",
    name: "Support",
    lifecycle_state: "published",
    attention_reasons: [],
    conversations: { total: 12, open: 4, pending: 1, human_handling: 1 },
    knowledge: { total: 1, truncated: false, items: [{ id: 4, name: "Policy", kind: "policy", state: "ready" }] },
    channels: {
      web: { total: 1, truncated: false, items: [{ id: 8, provider: "web", display_name: "Website", lifecycle_state: "active", health_state: "healthy", enabled: true, active_revision_id: 2 }] },
      facebook: { total: 0, truncated: false, items: [] },
      zalo: { total: 0, truncated: false, items: [] },
    },
    catalog_scope: {
      available: false,
      locations: { total: 0, truncated: false, all_accessible: true, items: [] },
      collections: { total: 0, truncated: false, all_accessible: true, items: [] },
    },
  }],
} as unknown as WorkspaceOverview;

describe("buildWorldModel", () => {
  it("changes information density by semantic level and projection", () => {
    const topology = buildWorldModel(overview, "system", "topology");
    const system = buildWorldModel(overview, "system", "structure");
    const agents = buildWorldModel(overview, "agents", "structure");

    expect(topology.nodes.map((node) => node.kind)).toEqual(["agent"]);
    expect(system.nodes.some((node) => node.kind === "activity")).toBe(true);
    expect(system.nodes.some((node) => node.id.startsWith("knowledge-group:"))).toBe(true);
    expect(agents.nodes.some((node) => node.id === "knowledge:agent-1:4")).toBe(true);
    expect(agents.nodes.some((node) => node.kind === "activity")).toBe(false);
    expect(new Set(agents.nodes.map((node) => node.id)).size).toBe(agents.nodes.length);
    expect(agents.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y))).toBe(true);
  });

  it("keeps shared resources distinct inside each Agent cluster", () => {
    const sharedOverview = {
      ...overview,
      agents: [
        overview.agents[0],
        { ...overview.agents[0], public_id: "agent-2", name: "Sales" },
      ],
    } as unknown as WorkspaceOverview;

    const model = buildWorldModel(sharedOverview, "agents", "structure");

    expect(model.nodes.filter((node) => node.kind === "knowledge")).toHaveLength(2);
    expect(model.nodes.filter((node) => node.kind === "channel")).toHaveLength(2);
    expect(new Set(model.nodes.map((node) => node.id)).size).toBe(model.nodes.length);
  });
});
