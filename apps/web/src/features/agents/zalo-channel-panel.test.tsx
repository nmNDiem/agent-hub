import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type ZaloConnection } from "@/lib/api";

import { ZaloChannelPanel } from "./zalo-channel-panel";

const mocks = vi.hoisted(() => ({
  listZaloConnections: vi.fn(),
  startZaloOAuth: vi.fn(),
  setZaloWebhookSecret: vi.fn(),
  verifyZaloConnection: vi.fn(),
  revokeZaloConnection: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, ...mocks } };
});

const connection: ZaloConnection = {
  id: 7,
  provider: "zalo",
  display_name: "ND Shop OA",
  external_account_id: "oa-123",
  lifecycle_state: "active",
  health_state: "webhook_subscription_failure",
  webhook_configured: false,
  agent_public_id: "agent-1",
  agent_name: "Trợ lý bán hàng",
  last_verified_at: "2026-10-14T01:00:00Z",
  created_at: "2026-10-14T00:00:00Z",
  updated_at: "2026-10-14T01:00:00Z",
};

describe("ZaloChannelPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listZaloConnections.mockResolvedValue({ items: [] });
  });

  it("starts OAuth without rendering token inputs", async () => {
    mocks.startZaloOAuth.mockReturnValue(new Promise(() => undefined));
    render(<ZaloChannelPanel canWrite publicAgentId="agent-1" workspaceId="workspace-1" />);

    expect(await screen.findByText("Chưa có Zalo OA")).toBeInTheDocument();
    expect(screen.queryByLabelText(/access token/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Kết nối bằng Zalo OAuth" }));

    expect(mocks.startZaloOAuth).toHaveBeenCalledWith("workspace-1", {
      agent_public_id: "agent-1",
    });
  });

  it("stores the separate webhook secret through a password field", async () => {
    mocks.listZaloConnections.mockResolvedValue({ items: [connection] });
    mocks.setZaloWebhookSecret.mockResolvedValue({
      ...connection,
      health_state: "healthy",
      webhook_configured: true,
    });
    render(<ZaloChannelPanel canWrite publicAgentId="agent-1" workspaceId="workspace-1" />);

    expect(await screen.findByText("Cần cấu hình webhook")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Nhập OA secret" }));
    const secret = screen.getByLabelText(/OA secret key/);
    expect(secret).toHaveAttribute("type", "password");
    fireEvent.change(secret, { target: { value: "oa-webhook-secret-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu bí mật" }));

    await waitFor(() => expect(mocks.setZaloWebhookSecret).toHaveBeenCalledWith(
      "workspace-1",
      7,
      "oa-webhook-secret-123",
    ));
    expect(await screen.findByText("Hoạt động tốt")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("oa-webhook-secret-123")).not.toBeInTheDocument();
  });

  it("keeps mutation controls unavailable for read-only members", async () => {
    mocks.listZaloConnections.mockResolvedValue({ items: [connection] });
    render(<ZaloChannelPanel canWrite={false} publicAgentId="agent-1" workspaceId="workspace-1" />);

    expect(await screen.findByText("ND Shop OA")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nhập OA secret" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Thu hồi" })).not.toBeInTheDocument();
  });
});
