import { describe, expect, it } from "vitest";

import { agentSelection } from "./world-selection";

describe("agentSelection", () => {
  it("keeps Agent lifecycle state independent from related attention state", () => {
    const agent = {
      public_id: "sales",
      name: "Sales",
      lifecycle_state: "published",
      attention_reasons: ["handover_pending"],
    } as const;
    const selection = agentSelection(
      { workspace_slug: "lotus" },
      agent,
    );

    expect(selection).toMatchObject({ id: "agent:sales", state: "active", agentPublicId: "sales" });
    expect(selection).not.toHaveProperty("x");
    expect(selection).not.toHaveProperty("y");
  });
});
