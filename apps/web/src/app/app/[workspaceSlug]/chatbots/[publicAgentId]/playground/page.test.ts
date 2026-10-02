import { describe, expect, it, vi } from "vitest";

import Page from "./page";

const mocks = vi.hoisted(() => ({
  redirect: vi.fn(() => { throw new Error("NEXT_REDIRECT"); }),
}));

vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));

describe("legacy Playground route", () => {
  it("redirects to the unified chatbot management page", async () => {
    await expect(Page({
      params: Promise.resolve({
        workspaceSlug: "nd shop",
        publicAgentId: "agent/id",
      }),
    })).rejects.toThrow("NEXT_REDIRECT");

    expect(mocks.redirect).toHaveBeenCalledWith("/app/nd%20shop/chatbots?agent=agent%2Fid");
  });
});
