import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SystemShell } from "./system-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/fashion-shop/overview",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "fashion-shop",
  display_name: "Fashion Shop",
  timezone: "Asia/Ho_Chi_Minh",
  role: "owner" as const,
  created_at: "2026-09-21T00:00:00Z",
};

describe("SystemShell", () => {
  it("treats World as the workspace system instead of a navigation tab", () => {
    render(<SystemShell
      overview={{ capabilities: { catalog: { available: false, can_setup: false } } }}
      user={{ id: "user", email: "owner@example.com", email_verified: false }}
      workspace={workspace}
      workspaces={[workspace]}
    ><h1>Hệ thống</h1></SystemShell>);

    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Chọn workspace" })).toHaveValue("fashion-shop");
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "World" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inbox" })).toBeInTheDocument();
    expect(screen.queryByText("Catalog")).not.toBeInTheDocument();
  });

  it("exposes authorized Commerce areas through the system launcher", () => {
    render(<SystemShell
      overview={{ capabilities: { catalog: { available: true, can_setup: false } } }}
      user={{ id: "user", email: "owner@example.com", email_verified: false }}
      workspace={workspace}
      workspaces={[workspace]}
    ><h1>Hệ thống</h1></SystemShell>);

    expect(screen.getByText("Catalog")).toBeInTheDocument();
    expect(screen.getByText("Địa điểm")).toBeInTheDocument();
    expect(screen.getByText("Bộ sưu tập")).toBeInTheDocument();
  });
});
