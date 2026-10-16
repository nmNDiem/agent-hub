import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

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

describe("AppShell", () => {
  it("renders the authorized workspace and marks future modules unavailable", () => {
    render(
      <AppShell
        overview={{ capabilities: { catalog: { available: false } } } as never}
        user={{
          id: "01992f3c-4436-7000-8000-000000000002",
          email: "owner@example.com",
          email_verified: false,
        }}
        workspace={workspace}
        workspaces={[workspace]}
      >
        <h1>Tổng quan</h1>
      </AppShell>,
    );
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Chọn workspace" })).toHaveValue("fashion-shop");
    expect(screen.getAllByText("Agents")).not.toHaveLength(0);
    expect(screen.queryByText("Catalog")).not.toBeInTheDocument();
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });

  it("shows Commerce navigation only when the server projection enables it", () => {
    render(
      <AppShell
        overview={{ capabilities: { catalog: { available: true } } } as never}
        user={{
          id: "01992f3c-4436-7000-8000-000000000002",
          email: "owner@example.com",
          email_verified: false,
        }}
        workspace={workspace}
        workspaces={[workspace]}
      >
        <h1>World</h1>
      </AppShell>,
    );

    expect(screen.getAllByRole("link", { name: "Catalog" })).not.toHaveLength(0);
    expect(screen.getAllByRole("link", { name: "Locations" })).not.toHaveLength(0);
    expect(screen.getAllByRole("link", { name: "Collections" })).not.toHaveLength(0);
  });
});
