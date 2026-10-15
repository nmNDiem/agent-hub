import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsPage } from "./analytics-page";

const mocks = vi.hoisted(() => ({
  getAnalytics: vi.fn(),
  getMe: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "fashion-shop" }),
  usePathname: () => "/app/fashion-shop/analytics",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getAnalytics: mocks.getAnalytics,
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

const report = {
  days: 7 as const,
  timezone: "Asia/Ho_Chi_Minh",
  period_started_at: "2026-10-08T17:00:00Z",
  period_ends_at: "2026-10-15T12:00:00Z",
  channel: null,
  agent_public_id: null,
  summary: { conversations: 8, inbound_messages: 15, completed_replies: 12, failed_replies: 1 },
  first_response: { average_seconds: 42, sample_count: 7 },
  human_response: { average_seconds: null, sample_count: 0 },
  resolution: { ai_only_resolved: 3, human_handled_resolved: 2, unresolved: 3, handoffs: 2 },
  lead_conversion: { converted_conversations: 2, eligible_conversations: 8, rate: 0.25 },
  activity: [
    { date: "2026-10-14", conversations: 3, inbound_messages: 5, completed_replies: 4 },
    { date: "2026-10-15", conversations: 5, inbound_messages: 10, completed_replies: 8 },
  ],
  by_channel: [
    { key: "web", label: "Web", conversations: 5, inbound_messages: 10, completed_replies: 8, delivery: null },
    { key: "facebook", label: "Facebook", conversations: 3, inbound_messages: 5, completed_replies: 4, delivery: { accepted: 1, delivered: 2, failed_retryable: 0, failed_terminal: 1 } },
  ],
  by_agent: [
    { key: "agent-1", label: "Trợ lý bán hàng", conversations: 8, inbound_messages: 15, completed_replies: 12, delivery: { accepted: 1, delivered: 2, failed_retryable: 0, failed_terminal: 1 } },
  ],
  product_interest: [
    { product_id: 7, product_name: "Áo khoác linen", impressions: 4, conversations: 3 },
  ],
  agent_options: [{ public_id: "agent-1", name: "Trợ lý bán hàng" }],
};

function me(role: "owner" | "member" = "owner") {
  return {
    user: { id: "user", email: "owner@example.com", email_verified: true },
    workspaces: [{ ...workspace, role }],
  };
}

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue(me());
    mocks.getAnalytics.mockResolvedValue(report);
  });

  it("renders persisted metrics and reloads filters", async () => {
    render(<AnalyticsPage />);

    expect(await screen.findByText("42 giây")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByText("Áo khoác linen")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /Hoạt động và kết quả giao theo kênh/ })).toBeInTheDocument();
    expect(mocks.getAnalytics).toHaveBeenCalledWith(workspace.id, {
      days: 7,
      channel: undefined,
      agentPublicId: undefined,
    });

    fireEvent.change(screen.getByLabelText("Kênh"), { target: { value: "facebook" } });
    await waitFor(() => expect(mocks.getAnalytics).toHaveBeenLastCalledWith(workspace.id, {
      days: 7,
      channel: "facebook",
      agentPublicId: undefined,
    }));
    fireEvent.click(screen.getByRole("button", { name: "30 ngày" }));
    await waitFor(() => expect(mocks.getAnalytics).toHaveBeenLastCalledWith(workspace.id, {
      days: 30,
      channel: "facebook",
      agentPublicId: undefined,
    }));
  });

  it("renders the empty persisted-data state", async () => {
    mocks.getAnalytics.mockResolvedValue({
      ...report,
      summary: { conversations: 0, inbound_messages: 0, completed_replies: 0, failed_replies: 0 },
      resolution: { ai_only_resolved: 0, human_handled_resolved: 0, unresolved: 0, handoffs: 0 },
      lead_conversion: { converted_conversations: 0, eligible_conversations: 0, rate: null },
      by_channel: [],
      by_agent: [],
      product_interest: [],
    });
    render(<AnalyticsPage />);
    expect(await screen.findByText("Chưa có hoạt động trong kỳ")).toBeInTheDocument();
    expect(screen.getAllByText("Chưa có dữ liệu")).toHaveLength(2);
  });

  it("shows forbidden without requesting analytics for a member", async () => {
    mocks.getMe.mockResolvedValue(me("member"));
    render(<AnalyticsPage />);
    expect(await screen.findByText("Không có quyền truy cập")).toBeInTheDocument();
    expect(mocks.getAnalytics).not.toHaveBeenCalled();
  });

  it("shows a safe load error", async () => {
    mocks.getAnalytics.mockRejectedValue(new Error("network"));
    render(<AnalyticsPage />);
    expect(await screen.findByText("Không thể tải dữ liệu phân tích.")).toBeInTheDocument();
  });
});
