import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceOverview } from "./workspace-overview";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getMe: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "fashion-shop" }),
  usePathname: () => "/app/fashion-shop/overview",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getDashboard: mocks.getDashboard,
      getMe: mocks.getMe,
    },
  };
});

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "fashion-shop",
  display_name: "Fashion Shop",
  timezone: "Asia/Ho_Chi_Minh",
  role: "owner" as const,
  created_at: "2026-09-21T00:00:00Z",
};

const dashboard = {
  days: 7 as const,
  timezone: "Asia/Ho_Chi_Minh",
  total_conversations: 12,
  assistant_messages: 23,
  active_agents: 2,
  enabled_web_channels: 2,
  activity: [
    { date: "2026-10-04", conversations: 4 },
    { date: "2026-10-05", conversations: 8 },
  ],
  recent_conversations: [],
  recent_leads: [],
  usage: {
    period_started_at: "2026-09-30T17:00:00Z",
    period_ends_at: "2026-10-31T17:00:00Z",
    timezone: "Asia/Ho_Chi_Minh",
    generated_turns: 125,
    generated_turn_limit: 1000,
    generated_turns_remaining: 875,
    generation_model_calls: 120,
    vision_model_calls: 5,
    tool_calls: 8,
    input_tokens: 1000,
    output_tokens: 500,
    total_tokens: 1500,
  },
};

describe("WorkspaceOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.getDashboard.mockResolvedValue(dashboard);
  });

  it("renders real dashboard aggregates and reloads the selected period", async () => {
    render(<WorkspaceOverview />);

    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("125 / 1.000")).toBeInTheDocument();
    expect(screen.getByText(/120 generation calls · 5 vision calls/)).toBeInTheDocument();
    expect(screen.getByText("Chưa có hội thoại")).toBeInTheDocument();
    expect(screen.getByText("Chưa có yêu cầu liên hệ")).toBeInTheDocument();
    expect(mocks.getDashboard).toHaveBeenCalledWith(workspace.id, 7);

    fireEvent.click(screen.getByRole("button", { name: "30 ngày" }));
    await waitFor(() => expect(mocks.getDashboard).toHaveBeenCalledWith(workspace.id, 30));
  });
});
