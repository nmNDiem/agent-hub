import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationsPage } from "./conversations-page";

const mocks = vi.hoisted(() => ({
  getConversation: vi.fn(),
  getMe: vi.fn(),
  listInboxMembers: vi.fn(),
  listAgents: vi.fn(),
  listConversations: vi.fn(),
  markConversationRead: vi.fn(),
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
      listInboxMembers: mocks.listInboxMembers,
      listAgents: mocks.listAgents,
      listConversations: mocks.listConversations,
      markConversationRead: mocks.markConversationRead,
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
  workflow_status: "open" as const,
  handling_mode: "ai" as const,
  state_version: 1,
  assigned_member_id: null,
  assigned_member_email: null,
  unread_count: 1,
  tags: [],
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
    mocks.listInboxMembers.mockResolvedValue({ items: [{ id: 1, user_id: "user", email: "admin@example.com", role: "admin" }] });
    mocks.markConversationRead.mockResolvedValue(undefined);
    mocks.getConversation.mockResolvedValue({
      conversation,
      retention_until: "2026-11-04T08:00:00Z",
      messages: [
        {
          id: 1,
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
          delivery: null,
        },
        {
          id: 2,
          role: "assistant",
          text: "Mình đã tìm thấy một số lựa chọn phù hợp.",
          status: "completed",
          created_at: "2026-10-05T08:01:00Z",
          completed_at: "2026-10-05T08:01:00Z",
          attachment: null,
          products: [],
          sources: [],
          delivery: null,
        },
      ],
      notes: [],
      follow_up: {
        lead_id: 7,
        source_channel: "web",
        capture_source: "agent_action",
        revision_no: 2,
        action_status: "succeeded",
        action_replayed: false,
        requested_at: "2026-10-05T08:00:00Z",
        followup_status: "new",
      },
    });
  });

  it("shows the unified inbox and marks the selected thread read", async () => {
    render(<ConversationsPage />);

    expect(await screen.findByText("Mình đã tìm thấy một số lựa chọn phù hợp.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tiếp quản" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nội dung trả lời" })).toBeDisabled();
    expect(screen.getByRole("region", { name: "Yêu cầu liên hệ" })).toHaveTextContent(
      "Agent action · revision 2",
    );
    await waitFor(() => expect(mocks.getConversation).toHaveBeenCalledWith(
      workspace.id,
      conversation.public_id,
    ));
    await waitFor(() => expect(mocks.markConversationRead).toHaveBeenCalledWith(
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
