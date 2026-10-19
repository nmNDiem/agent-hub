import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useWorkspace } from "@/lib/use-workspace";

import { WorkspaceSystemBoundary } from "./workspace-system-boundary";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  getWorkspaceOverview: vi.fn(),
  router: { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/lotus/overview",
  useRouter: () => mocks.router,
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getMe: mocks.getMe,
      getWorkspaceOverview: mocks.getWorkspaceOverview,
    },
  };
});

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "lotus",
  display_name: "Lotus",
  timezone: "Asia/Ho_Chi_Minh",
  role: "owner" as const,
  created_at: "2026-10-19T00:00:00Z",
};

function FocusedView() {
  const { workspace: current } = useWorkspace(workspace.slug);
  return <h1>{current?.display_name}</h1>;
}

describe("WorkspaceSystemBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.getWorkspaceOverview.mockResolvedValue({
      capabilities: { catalog: { available: false, can_setup: false } },
    });
  });

  it("shares workspace identity and overview instead of reloading them in focused views", async () => {
    render(<WorkspaceSystemBoundary workspaceSlug={workspace.slug}><FocusedView /></WorkspaceSystemBoundary>);

    expect(await screen.findByRole("heading", { name: "Lotus" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.getWorkspaceOverview).toHaveBeenCalledWith(workspace.id, 7));
    expect(mocks.getMe).toHaveBeenCalledTimes(1);
    expect(mocks.getWorkspaceOverview).toHaveBeenCalledTimes(1);
  });
});
