import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeadsPage } from "./leads-page";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  listLeads: vi.fn(),
  updateLeadStatus: vi.fn(),
  getLead: vi.fn(),
  updateLeadQualification: vi.fn(),
  exportLeads: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "fashion-shop" }),
  usePathname: () => "/app/fashion-shop/leads",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getMe: mocks.getMe,
      listLeads: mocks.listLeads,
      updateLeadStatus: mocks.updateLeadStatus,
      getLead: mocks.getLead,
      updateLeadQualification: mocks.updateLeadQualification,
      exportLeads: mocks.exportLeads,
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

const lead = {
  id: 7,
  conversation_public_id: "01992f3c-4436-7000-8000-000000000099",
  agent_public_id: "01992f3c-4436-7000-8000-000000000088",
  agent_name: "Trợ lý bán hàng",
  name: "Nguyễn An",
  email: "an@example.com",
  phone: null,
  source_channel: "web" as const,
  capture_source: "agent_action" as const,
  revision_no: 2,
  action_status: "succeeded" as const,
  action_replayed: true,
  consent_at: "2026-10-04T08:00:00Z",
  consent_text_version: "vi-VN:contact-v1:30d",
  followup_status: "new" as const,
  qualification_status: "pending_review" as const,
  qualification_version: 1,
  qualification_reason: null,
  qualification_updated_at: null,
  intake: {
    public_id: "01992f3c-4436-7000-8000-000000000077",
    purpose: "Tư vấn giải pháp phù hợp",
    submitted_at: "2026-10-04T08:00:00Z",
    action_status: "succeeded" as const,
    action_replayed: true,
  },
  retention_until: "2026-11-03T08:00:00Z",
  created_at: "2026-10-04T08:00:00Z",
  updated_at: "2026-10-04T08:00:00Z",
};

describe("LeadsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.listLeads.mockResolvedValue({ items: [lead], next_cursor: null });
    mocks.updateLeadStatus.mockResolvedValue({ ...lead, followup_status: "contacted" });
    mocks.getLead.mockResolvedValue({
      lead,
      intake: {
        ...lead.intake,
        disclosure_version: "intake-v1-example",
        answers: [
          { field_key: "01992f3c-4436-7000-8000-000000000066", label: "Nhu cầu", value: "Tư vấn gói phù hợp" },
        ],
      },
    });
    mocks.updateLeadQualification.mockResolvedValue({
      ...lead,
      qualification_status: "qualified",
      qualification_version: 2,
    });
    mocks.exportLeads.mockResolvedValue(new Blob(["lead_id\n7"], { type: "text/csv" }));
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:leads");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("expands intake answers and keeps qualification human-owned", async () => {
    render(<LeadsPage />);
    await screen.findByText("Nguyễn An");
    fireEvent.click(screen.getByRole("button", { name: "Intake" }));

    expect(await screen.findByText("Tư vấn gói phù hợp")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Đánh giá của nhân viên"), {
      target: { value: "qualified" },
    });

    await waitFor(() => expect(mocks.updateLeadQualification).toHaveBeenCalledWith(
      workspace.id,
      lead.id,
      "qualified",
      1,
    ));
  });

  it("shows consented contact data and updates follow-up status", async () => {
    render(<LeadsPage />);
    expect(await screen.findByText("Nguyễn An")).toBeInTheDocument();
    expect(screen.getByText("an@example.com")).toBeInTheDocument();
    expect(screen.getByText(/Agent action · revision 2/)).toBeInTheDocument();
    expect(screen.getByText(/succeeded · replay/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Trạng thái của Nguyễn An"), {
      target: { value: "contacted" },
    });
    await waitFor(() => expect(mocks.updateLeadStatus).toHaveBeenCalledWith(
      workspace.id,
      lead.id,
      "contacted",
    ));
    expect(await screen.findByText("Đã cập nhật trạng thái theo dõi.")).toBeInTheDocument();
  });

  it("keeps the honest empty state when no visitor consent exists", async () => {
    mocks.listLeads.mockResolvedValue({ items: [], next_cursor: null });
    render(<LeadsPage />);
    expect(await screen.findByText("Chưa có yêu cầu liên hệ")).toBeInTheDocument();
    expect(screen.getByText(/vẫn có thể chat/)).toBeInTheDocument();
  });
});
