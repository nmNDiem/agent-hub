import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type FacebookConnection } from "@/lib/api";

import { FacebookChannelPanel } from "./facebook-channel-panel";

const mocks = vi.hoisted(() => ({
  listFacebookConnections: vi.fn(),
  connectFacebook: vi.fn(),
  verifyFacebookConnection: vi.fn(),
  reauthorizeFacebookConnection: vi.fn(),
  revokeFacebookConnection: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, ...mocks } };
});

const connection: FacebookConnection = {
  id: 4,
  provider: "facebook",
  display_name: "ND Shop",
  external_account_id: "page-123",
  lifecycle_state: "active",
  health_state: "permission_expired",
  agent_public_id: "agent-1",
  agent_name: "Trợ lý bán hàng",
  latest_queue_state: "completed",
  latest_delivery_state: "accepted",
  latest_safe_error_code: "FACEBOOK_PERMISSION_EXPIRED",
  last_verified_at: "2026-10-08T01:00:00Z",
  created_at: "2026-10-08T00:00:00Z",
  updated_at: "2026-10-08T01:00:00Z",
};

describe("FacebookChannelPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listFacebookConnections.mockResolvedValue({ items: [] });
  });

  it("renders loading and empty states with a write-only token field", async () => {
    render(<FacebookChannelPanel canWrite publicAgentId="agent-1" workspaceId="workspace-1" />);
    expect(screen.getByText("Đang tải kết nối Facebook…")).toBeInTheDocument();
    expect(await screen.findByText("Chưa có Facebook Page")).toBeInTheDocument();
    expect(screen.getByLabelText("Page access token")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Page access token")).toHaveAttribute("autocomplete", "new-password");
  });

  it("shows permission and operational state, then clears a token after reauthorization", async () => {
    mocks.listFacebookConnections.mockResolvedValue({ items: [connection] });
    mocks.reauthorizeFacebookConnection.mockResolvedValue({
      ...connection,
      health_state: "healthy",
      latest_safe_error_code: null,
    });
    render(<FacebookChannelPanel canWrite publicAgentId="agent-1" workspaceId="workspace-1" />);

    expect(await screen.findByText("Quyền đã hết hạn")).toBeInTheDocument();
    expect(screen.getByText("Facebook đã nhận")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Xác thực lại" }));
    const token = screen.getByLabelText("Page access token mới");
    expect(token).toHaveAttribute("type", "password");
    fireEvent.change(token, { target: { value: "new-secret-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Thay credential" }));

    await waitFor(() => expect(mocks.reauthorizeFacebookConnection).toHaveBeenCalledWith(
      "workspace-1",
      4,
      "new-secret-token",
    ));
    expect(await screen.findByText("Hoạt động tốt")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("new-secret-token")).not.toBeInTheDocument();
  });

  it("keeps controls unavailable for read-only members", async () => {
    mocks.listFacebookConnections.mockResolvedValue({ items: [connection] });
    render(<FacebookChannelPanel canWrite={false} publicAgentId="agent-1" workspaceId="workspace-1" />);
    expect(await screen.findByText("ND Shop")).toBeInTheDocument();
    expect(screen.queryByLabelText("Page access token")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Thu hồi" })).not.toBeInTheDocument();
  });
});
