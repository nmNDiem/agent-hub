import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "./auth-form";

const mocks = vi.hoisted(() => ({ replace: vi.fn(), login: vi.fn(), register: vi.fn(), getMe: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace, refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams("next=//attacker.example"),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, login: mocks.login, register: mocks.register, getMe: mocks.getMe } };
});

describe("AuthForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.login.mockResolvedValue({});
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: false },
      workspaces: [{ slug: "fashion-shop" }],
    });
  });

  it("logs in and rejects an unsafe return destination", async () => {
    render(<AuthForm mode="login" />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "password" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    await waitFor(() => expect(mocks.login).toHaveBeenCalledWith("owner@example.com", "password"));
    expect(mocks.replace).toHaveBeenCalledWith("/app/fashion-shop/overview");
  });

  it("shows and applies the eight-character registration minimum", () => {
    render(<AuthForm mode="register" />);

    expect(screen.getByLabelText(/Mật khẩu/, { selector: 'input[name="password"]' })).toHaveAttribute("minLength", "8");
    expect(screen.getByLabelText(/Xác nhận mật khẩu/, { selector: 'input[name="confirmPassword"]' })).toHaveAttribute("minLength", "8");
    expect(screen.getByText(/Tối thiểu 8 ký tự/)).toBeInTheDocument();
  });
});
