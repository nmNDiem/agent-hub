import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FeedbackBanner } from "./feedback-banner";

describe("FeedbackBanner", () => {
  it("shows an actionable error with its support id", () => {
    const retry = vi.fn();
    render(<FeedbackBanner
      feedback={{
        kind: "error",
        message: "Không thể tải dữ liệu.",
        requestId: "req-123",
        retryable: true,
      }}
      onRetry={retry}
    />);

    expect(screen.getByRole("alert")).toHaveTextContent("Không thể tải dữ liệu.");
    expect(screen.getByText(/req-123/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("does not offer retry for a validation error", () => {
    render(<FeedbackBanner feedback={{ kind: "error", message: "Dữ liệu không hợp lệ." }} />);
    expect(screen.queryByRole("button", { name: "Thử lại" })).not.toBeInTheDocument();
  });
});
