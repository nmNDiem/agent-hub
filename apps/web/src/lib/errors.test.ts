import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { toUiError } from "@/lib/errors";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("toUiError", () => {
  it("keeps safe API context and logs only diagnostic metadata", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const error = new ApiError(
      503,
      "SERVICE_UNAVAILABLE",
      "Dịch vụ tạm thời không sẵn sàng.",
      { secret: "must-not-be-logged" },
      "req-support-123",
    );

    expect(toUiError(error, {
      operation: "agents.create",
      fallback: "Không thể tạo chatbot.",
    })).toEqual({
      kind: "error",
      message: "Dịch vụ tạm thời không sẵn sàng.",
      requestId: "req-support-123",
      retryable: true,
    });
    expect(consoleError).toHaveBeenCalledWith(
      "[AgentHub] Client operation failed",
      expect.objectContaining({
        operation: "agents.create",
        status: 503,
        code: "SERVICE_UNAVAILABLE",
        requestId: "req-support-123",
      }),
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain("must-not-be-logged");
  });

  it("uses a safe fallback for unexpected failures", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    expect(toUiError(new TypeError("internal detail"), {
      operation: "catalog.load",
      fallback: "Không thể tải catalog.",
    })).toMatchObject({
      kind: "error",
      message: "Không thể tải catalog.",
      retryable: true,
    });
  });
});
