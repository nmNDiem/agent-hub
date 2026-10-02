import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatbotsPage } from "./chatbots-page";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  listAgents: vi.fn(),
  listKnowledgeBases: vi.fn(),
  listLocations: vi.fn(),
  listCollections: vi.fn(),
  getAgentKnowledgeBases: vi.fn(),
  updateAgent: vi.fn(),
  replaceAgentCatalogScope: vi.fn(),
  replaceAgentKnowledgeBases: vi.fn(),
  createAgent: vi.fn(),
  streamPlaygroundMessage: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "fashion-shop" }),
  usePathname: () => "/app/fashion-shop/chatbots",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: mocks.replace, refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, ...mocks } };
});

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "fashion-shop",
  display_name: "Fashion Shop",
  timezone: "Asia/Ho_Chi_Minh",
  role: "owner" as const,
  created_at: "2026-09-21T00:00:00Z",
};

const agent = {
  public_id: "01992f3c-4436-7000-8000-000000000010",
  name: "Trợ lý",
  greeting: "Xin chào",
  safe_instructions: null,
  default_locale: "vi",
  status: "draft" as const,
  catalog_scope: { location_ids: null, collection_ids: null },
  created_at: "2026-09-30T00:00:00Z",
  updated_at: "2026-09-30T00:00:00Z",
};

describe("ChatbotsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.listAgents.mockResolvedValue({ items: [agent] });
    mocks.listKnowledgeBases.mockResolvedValue({
      items: [{ id: 5, name: "FAQ", kind: "faq", status: "active", active_embedding_profile_id: 1, target_embedding_profile_id: null, document_count: 2, created_at: agent.created_at, updated_at: agent.updated_at }],
      next_cursor: null,
    });
    mocks.listLocations.mockResolvedValue([{ id: 2, name: "Hà Nội", code: "HN", type: "store", address: {}, metadata: {}, is_active: true, archived_at: null, created_at: agent.created_at, updated_at: agent.updated_at }]);
    mocks.listCollections.mockResolvedValue([]);
    mocks.getAgentKnowledgeBases.mockResolvedValue({ public_agent_id: agent.public_id, knowledge_base_ids: [] });
    mocks.updateAgent.mockResolvedValue({ ...agent, safe_instructions: "Thân thiện" });
    mocks.replaceAgentCatalogScope.mockResolvedValue(agent);
    mocks.replaceAgentKnowledgeBases.mockResolvedValue({ public_agent_id: agent.public_id, knowledge_base_ids: [5] });
  });

  it("persists agent behavior, catalog scope and knowledge assignments", async () => {
    render(<ChatbotsPage />);
    expect(await screen.findByRole("combobox", { name: "Đổi chatbot" })).toHaveValue(agent.public_id);
    expect(screen.getByRole("heading", { name: "Thử chatbot" })).toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText("Giọng điệu và hướng dẫn an toàn"), {
      target: { value: "Thân thiện" },
    });
    fireEvent.click(screen.getByText("FAQ").closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByLabelText(/Tất cả location đang hoạt động/));
    fireEvent.click(screen.getByText("Hà Nội").closest("label")!.querySelector("input")!);
    fireEvent.click(screen.getByRole("button", { name: "Lưu cấu hình" }));

    await waitFor(() => expect(mocks.updateAgent).toHaveBeenCalledWith(
      workspace.id,
      agent.public_id,
      expect.objectContaining({ safe_instructions: "Thân thiện" }),
    ));
    expect(mocks.replaceAgentCatalogScope).toHaveBeenCalledWith(
      workspace.id,
      agent.public_id,
      { location_ids: [2], collection_ids: null },
    );
    expect(mocks.replaceAgentKnowledgeBases).toHaveBeenCalledWith(
      workspace.id,
      agent.public_id,
      [5],
    );
  });
});
