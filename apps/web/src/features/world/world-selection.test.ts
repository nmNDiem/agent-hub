import { describe, expect, it } from "vitest";

import { agentSelection } from "./world-selection";

describe("agentSelection", () => {
  it("maps authoritative lifecycle and attention state without layout coordinates", () => {
    const selection = agentSelection(
      { workspace_slug: "lotus" },
      { public_id: "sales", name: "Sales", lifecycle_state: "published", attention_reasons: ["handover_pending"] },
    );

    expect(selection).toMatchObject({ id: "agent:sales", state: "attention", agentPublicId: "sales" });
    expect(selection).not.toHaveProperty("x");
    expect(selection).not.toHaveProperty("y");
  });
});
