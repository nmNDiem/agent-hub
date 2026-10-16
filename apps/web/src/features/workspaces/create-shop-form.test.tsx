import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CreateShopForm } from "./create-shop-form";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  getMe: vi.fn(),
  createWorkspace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace, refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: { ...original.api, getMe: mocks.getMe, createWorkspace: mocks.createWorkspace },
  };
});

describe("CreateShopForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({ user: {}, workspaces: [] });
    mocks.createWorkspace.mockResolvedValue({ slug: "cua-hang-lume" });
  });

  it("suggests a normalized slug and creates the owner workspace", async () => {
    render(<CreateShopForm />);
    const name = await screen.findByLabelText("Tên workspace");
    fireEvent.change(name, { target: { value: "Cửa hàng Lumé" } });
    expect(screen.getByLabelText(/Đường dẫn workspace/)).toHaveValue("cua-hang-lume");
    fireEvent.click(screen.getByRole("button", { name: "Tạo workspace" }));
    await waitFor(() =>
      expect(mocks.createWorkspace).toHaveBeenCalledWith({
        display_name: "Cửa hàng Lumé",
        slug: "cua-hang-lume",
      }),
    );
    expect(mocks.replace).toHaveBeenCalledWith("/app/cua-hang-lume/overview");
  });
});
