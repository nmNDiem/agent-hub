import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgePage } from "./knowledge-page";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  listKnowledgeBases: vi.fn(),
  listAgents: vi.fn(),
  listKnowledgeDocuments: vi.fn(),
  listKnowledgeVersions: vi.fn(),
  runKnowledgeDiagnostic: vi.fn(),
  retryIngestionJob: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "fashion-shop" }),
  usePathname: () => "/app/fashion-shop/knowledge",
  useRouter: () => ({ push: vi.fn(), replace: mocks.replace, refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getMe: mocks.getMe,
      listKnowledgeBases: mocks.listKnowledgeBases,
      listAgents: mocks.listAgents,
      listKnowledgeDocuments: mocks.listKnowledgeDocuments,
      listKnowledgeVersions: mocks.listKnowledgeVersions,
      runKnowledgeDiagnostic: mocks.runKnowledgeDiagnostic,
      retryIngestionJob: mocks.retryIngestionJob,
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

describe("KnowledgePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "prompt").mockReturnValue("Provider outage retry");
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.listKnowledgeBases.mockResolvedValue({
      items: [{
        id: 3,
        name: "Chính sách cửa hàng",
        kind: "policy",
        status: "active",
        active_embedding_profile_id: 1,
        target_embedding_profile_id: null,
        document_count: 1,
        created_at: "2026-09-30T00:00:00Z",
        updated_at: "2026-09-30T00:00:00Z",
      }],
      next_cursor: null,
    });
    mocks.listAgents.mockResolvedValue({ items: [] });
    mocks.listKnowledgeDocuments.mockResolvedValue({
      items: [{
        id: 9,
        knowledge_base_id: 3,
        title: "Đổi trả",
        kind: "policy",
        status: "active",
        source_kind: "manual",
        latest_version_id: 10,
        version_no: 1,
        mime_type: "text/plain",
        byte_size: 120,
        active_generation_id: null,
        active_version_no: null,
        reviewed_at: null,
        review_due_at: null,
        reviewed_by_user_id: null,
        freshness_state: "unknown",
        active_generation_changed: false,
        ingestion_job: {
          id: 12,
          document_id: 9,
          document_version_id: 10,
          target_generation_id: null,
          status: "failed",
          attempts: 1,
          last_error_code: "PROVIDER_TEMPORARY",
          retryable: true,
          scheduled_at: "2026-09-30T00:00:00Z",
          created_at: "2026-09-30T00:00:00Z",
          updated_at: "2026-09-30T00:00:00Z",
          completed_at: null,
          recovery_state: "retryable_failure",
        },
        created_at: "2026-09-30T00:00:00Z",
        updated_at: "2026-09-30T00:00:00Z",
      }],
      next_cursor: null,
    });
    mocks.listKnowledgeVersions.mockResolvedValue({
      items: [{
        id: 10,
        version_no: 1,
        source_kind: "manual",
        mime_type: "text/plain",
        byte_size: 120,
        content_sha256: "abc",
        created_by_user_id: "user",
        created_at: "2026-09-30T00:00:00Z",
        reviewed_at: null,
        review_due_at: null,
        reviewed_by_user_id: null,
        freshness_state: "unknown",
        generation_id: null,
        generation_status: null,
        generation_failure_code: null,
        is_active: false,
        ingestion_job: null,
      }],
      next_cursor: null,
    });
    mocks.runKnowledgeDiagnostic.mockResolvedValue({
      status: "completed",
      target_type: "knowledge_bases",
      resolved_knowledge_base_ids: [3],
      active_sources: [],
      hits: [],
      raw_hit_count: 0,
      discarded_hit_count: 0,
      reason_codes: ["NO_ACTIVE_READY_GENERATION"],
    });
    mocks.retryIngestionJob.mockResolvedValue({ status: "queued" });
  });

  it("renders an honest failed ingestion state and retries it", async () => {
    render(<KnowledgePage />);

    expect(await screen.findByText("Đổi trả")).toBeInTheDocument();
    expect(screen.getByText("Thất bại")).toBeInTheDocument();
    expect(screen.getByText("Mã lỗi: PROVIDER_TEMPORARY")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Thử lại Đổi trả" }));
    await waitFor(() => expect(mocks.retryIngestionJob).toHaveBeenCalledWith(
      workspace.id,
      12,
      "Provider outage retry",
    ));
  });

  it("shows latest-versus-active state, immutable history, and diagnostic reasons", async () => {
    render(<KnowledgePage />);

    expect(await screen.findByText(/Phiên bản mới nhất 1/)).toHaveTextContent("đang tìm kiếm chưa có");
    expect(screen.getByText(/Chưa xác nhận/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Chi tiết Đổi trả" }));
    expect(await screen.findByText("Lịch sử bất biến")).toBeInTheDocument();
    await waitFor(() => expect(mocks.listKnowledgeVersions).toHaveBeenCalledWith(workspace.id, 3, 9));

    fireEvent.change(screen.getByRole("textbox", { name: "Câu truy vấn" }), {
      target: { value: "chính sách đổi trả" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Chạy chẩn đoán" }));
    expect(await screen.findByText(/NO_ACTIVE_READY_GENERATION/)).toBeInTheDocument();
  });
});
