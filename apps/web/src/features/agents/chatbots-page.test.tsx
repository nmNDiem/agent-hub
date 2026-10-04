import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";

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
  getWidgetConfig: vi.fn(),
  updateWidgetConfig: vi.fn(),
  publishWidget: vi.fn(),
  pauseWidget: vi.fn(),
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

const createdAgent = {
  ...agent,
  public_id: "01992f3c-4436-7000-8000-000000000011",
  name: "Tư vấn viên mới",
  greeting: "Xin chào! Mình có thể giúp gì cho bạn?",
  safe_instructions: "Tư vấn thân thiện và tự nhiên.",
};

const widgetConfig = {
  public_agent_id: agent.public_id,
  display_name: "Trợ lý",
  greeting: "Xin chào",
  status: "draft" as const,
  brand_color: "#0F8F87",
  launcher_position: "right" as const,
  allowed_origins: [] as string[],
  handoff_url: null,
  handoff_label: null,
  enabled: false,
  draft_differs: false,
  readiness: {
    has_allowed_origin: false,
    has_catalog_scope: true,
    has_knowledge: false,
    can_publish: false,
  },
  active_revision: null,
  embed_snippet: null,
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
    mocks.createAgent.mockResolvedValue(createdAgent);
    mocks.replaceAgentCatalogScope.mockResolvedValue(agent);
    mocks.replaceAgentKnowledgeBases.mockResolvedValue({ public_agent_id: agent.public_id, knowledge_base_ids: [5] });
    mocks.getWidgetConfig.mockResolvedValue(widgetConfig);
    mocks.updateWidgetConfig.mockImplementation(async (_workspaceId, _agentId, payload) => ({
      ...widgetConfig,
      ...payload,
      readiness: { ...widgetConfig.readiness, has_allowed_origin: true, can_publish: true },
    }));
    mocks.publishWidget.mockResolvedValue({
      ...widgetConfig,
      status: "published",
      enabled: true,
      allowed_origins: ["https://shop.example.com"],
      readiness: { ...widgetConfig.readiness, has_allowed_origin: true, can_publish: true },
      active_revision: { revision_no: 1, published_at: "2026-10-04T00:00:00Z" },
      embed_snippet: '<script async src="http://127.0.0.1:4173/widget/v1/loader.js" data-agent-id="agent"></script>',
    });
    mocks.pauseWidget.mockResolvedValue({ ...widgetConfig, status: "paused", enabled: false });
  });

  it("persists agent behavior, catalog scope and knowledge assignments", async () => {
    render(<ChatbotsPage />);
    expect(await screen.findByRole("combobox", { name: "Đổi chatbot" })).toHaveValue(agent.public_id);
    expect(screen.getByRole("heading", { name: "Thử chatbot" })).toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText(/Tính cách và phong cách trả lời/), {
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

  it("creates a ready-to-use chatbot from only its name", async () => {
    render(<ChatbotsPage />);
    await screen.findByRole("combobox", { name: "Đổi chatbot" });

    const pageHeading = screen.getByRole("heading", { name: "Chatbot" }).closest("section")!;
    fireEvent.click(within(pageHeading).getByRole("button", { name: "Tạo chatbot" }));
    const nameInput = screen.getByLabelText("Tên chatbot mới");
    fireEvent.change(nameInput, {
      target: { value: "Tư vấn viên mới" },
    });
    fireEvent.click(within(nameInput.closest("form")!).getByRole("button", { name: "Tạo chatbot" }));

    await waitFor(() => expect(mocks.createAgent).toHaveBeenCalledWith(
      workspace.id,
      { name: "Tư vấn viên mới", default_locale: "vi" },
    ));
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Đổi chatbot" })).toHaveValue(createdAgent.public_id));
    expect(mocks.listAgents).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Đã tạo chatbot. Bạn có thể cấu hình và thử ngay bây giờ.")).toBeInTheDocument();
    expect(screen.queryByText("Không thể hoàn tất thao tác. Vui lòng thử lại.")).not.toBeInTheDocument();
  });

  it("keeps the entered name and shows a support id when creation fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    mocks.createAgent.mockRejectedValue(new ApiError(
      503,
      "SERVICE_UNAVAILABLE",
      "Dịch vụ tạm thời không sẵn sàng.",
      {},
      "req-create-agent",
    ));
    render(<ChatbotsPage />);
    await screen.findByRole("combobox", { name: "Đổi chatbot" });

    const pageHeading = screen.getByRole("heading", { name: "Chatbot" }).closest("section")!;
    fireEvent.click(within(pageHeading).getByRole("button", { name: "Tạo chatbot" }));
    const nameInput = screen.getByLabelText("Tên chatbot mới");
    fireEvent.change(nameInput, { target: { value: "Giữ lại tên này" } });
    fireEvent.click(within(nameInput.closest("form")!).getByRole("button", { name: "Tạo chatbot" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Dịch vụ tạm thời không sẵn sàng.");
    expect(screen.getByText(/req-create-agent/)).toBeInTheDocument();
    expect(nameInput).toHaveValue("Giữ lại tên này");
    expect(mocks.listAgents).toHaveBeenCalledTimes(1);
  });

  it("configures an exact website origin and publishes the web widget", async () => {
    render(<ChatbotsPage />);
    await screen.findByRole("combobox", { name: "Đổi chatbot" });

    fireEvent.click(screen.getByRole("button", { name: /Kênh Web/ }));
    expect(await screen.findByRole("heading", { name: "Widget trò chuyện" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Thêm website"), {
      target: { value: "https://SHOP.example.com/" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Thêm website" }));
    expect(screen.getAllByText("https://shop.example.com").length).toBeGreaterThan(1);

    fireEvent.click(screen.getAllByRole("button", { name: "Phát hành" })[0]);
    await waitFor(() => expect(mocks.updateWidgetConfig).toHaveBeenCalledWith(
      workspace.id,
      agent.public_id,
      expect.objectContaining({ allowed_origins: ["https://shop.example.com"] }),
    ));
    await waitFor(() => expect(mocks.publishWidget).toHaveBeenCalledWith(
      workspace.id,
      agent.public_id,
    ));
    expect(await screen.findByText("Widget đã được phát hành lên website.")).toBeInTheDocument();
    expect(screen.getByText("Đang hoạt động")).toBeInTheDocument();
  });
});
