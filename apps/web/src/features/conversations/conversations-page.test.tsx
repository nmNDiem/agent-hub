import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationsPage } from "./conversations-page";

const mocks = vi.hoisted(() => ({
  getConversation: vi.fn(),
  getMe: vi.fn(),
  listAgents: vi.fn(),
  listConversations: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({
    workspaceSlug: "fashion-shop",
    conversationPublicId: "01992f3c-4436-7000-8000-000000000099",
  }),
  usePathname: () => "/app/fashion-shop/conversations/01992f3c-4436-7000-8000-000000000099",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams("days=7"),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getConversation: mocks.getConversation,
      getMe: mocks.getMe,
      listAgents: mocks.listAgents,
      listConversations: mocks.listConversations,
    },
  };
});

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "fashion-shop",
  display_name: "Fashion Shop",
  timezone: "Asia/Ho_Chi_Minh",
  role: "admin" as const,
  created_at: "2026-09-21T00:00:00Z",
};

const conversation = {
  public_id: "01992f3c-4436-7000-8000-000000000099",
  channel: "web" as const,
  agent_public_id: "01992f3c-4436-7000-8000-000000000088",
  agent_name: "Trợ lý bán hàng",
  started_at: "2026-10-05T08:00:00Z",
  last_message_at: "2026-10-05T08:01:00Z",
  message_count: 2,
  last_visitor_preview: "Tôi cần tìm áo khoác",
};

describe("ConversationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "admin@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.listAgents.mockResolvedValue({
      items: [{ public_id: conversation.agent_public_id, name: conversation.agent_name }],
    });
    mocks.listConversations.mockResolvedValue({ items: [conversation], next_cursor: null });
    mocks.getConversation.mockResolvedValue({
      conversation,
      retention_until: "2026-11-04T08:00:00Z",
      messages: [
        {
          role: "user",
          text: "Tôi cần tìm áo khoác",
          status: "completed",
          created_at: "2026-10-05T08:00:00Z",
          completed_at: "2026-10-05T08:00:00Z",
          attachment: {
            content_type: "image/jpeg",
            width: 800,
            height: 600,
            byte_size: 204800,
            created_at: "2026-10-05T08:00:00Z",
          },
          products: [],
          sources: [],
        },
        {
          role: "assistant",
          text: "Mình đã tìm thấy một số lựa chọn phù hợp.",
          status: "completed",
          created_at: "2026-10-05T08:01:00Z",
          completed_at: "2026-10-05T08:01:00Z",
          attachment: null,
          products: [],
          sources: [],
        },
      ],
    });
  });

  it("shows a read-only transcript with safe image metadata", async () => {
    render(<ConversationsPage />);

    expect(await screen.findByText("Mình đã tìm thấy một số lựa chọn phù hợp.")).toBeInTheDocument();
    expect(screen.getByText("image/jpeg · 800×600 · 200 KiB")).toBeInTheDocument();
    expect(screen.getByText("Chỉ đọc")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.getConversation).toHaveBeenCalledWith(
      workspace.id,
      conversation.public_id,
    ));
  });

  it("shows an explicit detail error instead of an endless loading state", async () => {
    mocks.getConversation.mockRejectedValueOnce(new Error("unavailable"));

    render(<ConversationsPage />);

    expect(await screen.findByText("Không thể mở hội thoại")).toBeInTheDocument();
    expect(screen.getByText("Hãy thử tải lại trang hoặc chọn một hội thoại khác.")).toBeInTheDocument();
  });
});
