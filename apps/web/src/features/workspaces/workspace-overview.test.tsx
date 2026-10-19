import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkspaceOverview as WorkspaceOverviewData } from "@/lib/api";

import { WorkspaceOverview } from "./workspace-overview";

const mocks = vi.hoisted(() => ({
  getWorkspaceOverview: vi.fn(),
  getMe: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "knowledge-team" }),
  usePathname: () => "/app/knowledge-team/overview",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: mocks.replace, refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getWorkspaceOverview: mocks.getWorkspaceOverview,
      getMe: mocks.getMe,
    },
  };
});

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "knowledge-team",
  display_name: "Knowledge Team",
  timezone: "Asia/Ho_Chi_Minh",
  role: "owner" as const,
  created_at: "2026-09-21T00:00:00Z",
};

const overview = {
  workspace_id: workspace.id,
  workspace_slug: workspace.slug,
  workspace_name: workspace.display_name,
  role: "owner",
  generated_at: "2026-10-16T00:00:00Z",
  days: 7,
  window_started_at: "2026-10-10T00:00:00Z",
  capabilities: { catalog: { available: false, can_setup: true } },
  dependencies: {
    agents: { state: "ready", reason: null },
    knowledge: { state: "ready", reason: null },
    channels: { state: "ready", reason: null },
    conversations: { state: "ready", reason: null },
    catalog: { state: "ready", reason: null },
  },
  agent_total: 1,
  agents_truncated: false,
  agents: [{
    public_id: "01992f3c-4436-7000-8000-000000000010",
    name: "Support Agent",
    lifecycle_state: "published",
    updated_at: "2026-10-16T00:00:00Z",
    active_revision: { id: 1, revision_no: 1, published_at: "2026-10-16T00:00:00Z" },
    knowledge: { total: 1, truncated: false, items: [{ id: 3, name: "Policy", kind: "policy", state: "ready" }] },
    channels: {
      web: { total: 0, truncated: false, items: [] },
      facebook: { total: 0, truncated: false, items: [] },
      zalo: { total: 0, truncated: false, items: [] },
    },
    catalog_scope: {
      available: false,
      locations: { total: 0, truncated: false, all_accessible: true, items: [] },
      collections: { total: 0, truncated: false, all_accessible: true, items: [] },
    },
    website_readiness: { configured: false, has_allowed_origin: false, has_knowledge: true, has_catalog_scope: false, can_publish: false },
    conversations: { total: 9, open: 4, pending: 1, human_handling: 1 },
    attention_reasons: ["handover_pending"],
  }],
} satisfies WorkspaceOverviewData;

describe("WorkspaceOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.getWorkspaceOverview.mockResolvedValue(overview);
  });

  it("renders the authoritative knowledge-only World and contextual navigation", async () => {
    render(<WorkspaceOverview />);

    expect(await screen.findByRole("button", { name: /Support Agent/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Agents" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "30 ngày" })).not.toBeInTheDocument();
    expect(screen.getByText("Thiết lập Commerce")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Catalog" })).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Dữ liệu kinh doanh" })).not.toBeInTheDocument();
    expect(mocks.getWorkspaceOverview).toHaveBeenCalledWith(workspace.id, 7);
  });

  it("opens the Agent inspector", async () => {
    render(<WorkspaceOverview />);

    const agentButton = await screen.findByRole("button", { name: /Support Agent/ });
    agentButton.focus();
    fireEvent.click(agentButton);
    const inspector = screen.getByRole("dialog", { name: "Support Agent" });
    expect(inspector).toBeInTheDocument();
    const closeButton = within(inspector).getByRole("button", { name: "Đóng bảng chi tiết" });
    expect(closeButton).toHaveFocus();
    expect(screen.getByRole("link", { name: /Kiểm thử/ })).toBeInTheDocument();

    const inspectorLinks = within(inspector).getAllByRole("link");
    inspectorLinks[inspectorLinks.length - 1].focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Support Agent" })).not.toBeInTheDocument();
    expect(agentButton).toHaveFocus();
  });

  it("shows the business rail only from authorized Catalog scope", async () => {
    mocks.getWorkspaceOverview.mockResolvedValue({
      ...overview,
      capabilities: { catalog: { available: true, can_setup: false } },
      agents: [{
        ...overview.agents[0],
        catalog_scope: {
          available: true,
          collections: {
            total: 1,
            truncated: false,
            all_accessible: false,
            items: [{ id: 11, name: "Liệu trình" }],
          },
          locations: {
            total: 1,
            truncated: false,
            all_accessible: false,
            items: [{ id: 22, name: "Quận 7" }],
          },
        },
      }],
    });

    render(<WorkspaceOverview />);

    expect(await screen.findByRole("complementary", { name: "Dữ liệu kinh doanh" })).toBeInTheDocument();
    expect(screen.getByText("Liệu trình")).toBeInTheDocument();
    expect(screen.getByText("Quận 7")).toBeInTheDocument();
    expect(screen.queryByText(/đơn hàng/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/lịch hẹn/i)).not.toBeInTheDocument();
  });
});
