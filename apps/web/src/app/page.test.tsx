import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "./page";

const mocks = vi.hoisted(() => ({ getMe: vi.fn(), replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, getMe: mocks.getMe } };
});

describe("Home", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("opens the first workspace when the session is valid", async () => {
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: false },
      workspaces: [{ slug: "fashion-shop" }],
    });

    render(<Home />);

    await waitFor(() => {
      expect(mocks.replace).toHaveBeenCalledWith("/app/fashion-shop/overview");
    });
  });

  it("opens login when the session cannot be restored", async () => {
    mocks.getMe.mockRejectedValue(new Error("Unauthenticated"));

    render(<Home />);

    await waitFor(() => {
      expect(mocks.replace).toHaveBeenCalledWith("/login?next=/app");
    });
  });
});
