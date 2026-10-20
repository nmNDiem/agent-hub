import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContactsPage } from "./contacts-page";

const mocks = vi.hoisted(() => ({
  addContactNote: vi.fn(),
  getContact: vi.fn(),
  getMe: vi.fn(),
  listContacts: vi.fn(),
  listInboxMembers: vi.fn(),
  updateLeadStatus: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({
    workspaceSlug: "fashion-shop",
    contactPublicId: "01992f3c-4436-7000-8000-000000000077",
  }),
  usePathname: () => "/app/fashion-shop/contacts/01992f3c-4436-7000-8000-000000000077",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      addContactNote: mocks.addContactNote,
      getContact: mocks.getContact,
      getMe: mocks.getMe,
      listContacts: mocks.listContacts,
      listInboxMembers: mocks.listInboxMembers,
      updateLeadStatus: mocks.updateLeadStatus,
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

const contact = {
  public_id: "01992f3c-4436-7000-8000-000000000077",
  display_name: "Nguyễn An",
  lifecycle_state: "active" as const,
  state_version: 1,
  assigned_member_id: 1,
  assigned_member_email: "owner@example.com",
  channels: ["website", "facebook"] as Array<"website" | "facebook">,
  tags: [{ id: 3, name: "VIP" }],
  retention_until: "2026-11-13T08:00:00Z",
  updated_at: "2026-10-14T08:00:00Z",
};

describe("ContactsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.listInboxMembers.mockResolvedValue({
      items: [{ id: 1, user_id: "user", email: "owner@example.com", role: "owner" }],
    });
    mocks.listContacts.mockResolvedValue({ items: [contact], next_cursor: null });
    mocks.addContactNote.mockResolvedValue(undefined);
    mocks.updateLeadStatus.mockResolvedValue(undefined);
    mocks.getContact.mockResolvedValue({
      contact,
      canonical_public_id: null,
      identities: [
        {
          id: 1,
          provider: "website",
          identity_type: "email",
          value: "an@example.com",
          verification_state: "consented",
          consent_at: "2026-10-14T08:00:00Z",
          consent_text_version: "vi-VN:contact-v1:30d",
          retention_until: contact.retention_until,
        },
        {
          id: 2,
          provider: "facebook",
          identity_type: "channel",
          value: null,
          verification_state: "provider_asserted",
          consent_at: null,
          consent_text_version: null,
          retention_until: contact.retention_until,
        },
      ],
      notes: [],
      timeline: [
        {
          key: "conversation:4",
          kind: "conversation",
          occurred_at: "2026-10-14T08:00:00Z",
          title: "Hội thoại facebook",
          detail: "Trợ lý bán hàng",
          conversation_public_id: "01992f3c-4436-7000-8000-000000000099",
          lead_id: null,
          source_channel: null,
          capture_source: null,
          revision_no: null,
          action_status: null,
          action_replayed: false,
        },
        {
          key: "lead:7",
          kind: "lead",
          occurred_at: "2026-10-14T07:00:00Z",
          title: "Yêu cầu liên hệ",
          detail: "new",
          conversation_public_id: null,
          lead_id: 7,
          source_channel: "facebook",
          capture_source: "agent_action",
          revision_no: 2,
          action_status: "succeeded",
          action_replayed: true,
        },
      ],
      duplicate_candidates: [
        {
          public_id: "01992f3c-4436-7000-8000-000000000078",
          display_name: "An Nguyễn",
          matching_identity_types: ["email"],
        },
      ],
      active_merges: [],
    });
  });

  it("shows consent-aware identities and the cross-channel timeline", async () => {
    render(<ContactsPage />);

    expect(await screen.findByText("an@example.com")).toBeInTheDocument();
    expect(screen.getByText("ID kênh được bảo vệ")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mở hội thoại" })).toHaveAttribute(
      "href",
      "/app/fashion-shop/conversations/01992f3c-4436-7000-8000-000000000099",
    );
    expect(screen.getByText("Hồ sơ có thể trùng")).toBeInTheDocument();
    expect(screen.getByText(/facebook · Agent action · revision 2 · succeeded · replay/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Trạng thái lead"), {
      target: { value: "contacted" },
    });
    await waitFor(() => expect(mocks.updateLeadStatus).toHaveBeenCalledWith(
      workspace.id,
      7,
      "contacted",
    ));
  });

  it("adds an internal note and refreshes the selected contact", async () => {
    render(<ContactsPage />);

    await screen.findByText("an@example.com");
    fireEvent.change(screen.getByLabelText("Ghi chú nội bộ"), {
      target: { value: "Ưu tiên gọi buổi sáng" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lưu ghi chú" }));
    await waitFor(() => expect(mocks.addContactNote).toHaveBeenCalledWith(
      workspace.id,
      contact.public_id,
      "Ưu tiên gọi buổi sáng",
    ));
    await waitFor(() => expect(mocks.getContact).toHaveBeenCalledTimes(2));
  });
});
