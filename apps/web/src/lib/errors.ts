import { ApiError } from "@/lib/api";

export type FeedbackKind = "error" | "warning" | "success" | "info";

export type UiFeedback = {
  kind: FeedbackKind;
  message: string;
  requestId?: string;
  retryable?: boolean;
};

type ErrorContext = {
  operation: string;
  fallback: string;
  retryable?: boolean;
};

export function feedback(kind: FeedbackKind, message: string): UiFeedback {
  return { kind, message };
}

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 429 || status >= 500;
}

export function reportClientError(error: unknown, operation: string): void {
  const diagnostic = error instanceof ApiError
    ? {
        operation,
        errorType: error.name,
        status: error.status,
        code: error.code,
        requestId: error.requestId,
      }
    : {
        operation,
        errorType: error instanceof Error ? error.name : "UnknownError",
      };

  if (process.env.NODE_ENV !== "production" && error instanceof Error && !(error instanceof ApiError)) {
    console.error("[AgentHub] Client operation failed", diagnostic, error);
    return;
  }
  console.error("[AgentHub] Client operation failed", diagnostic);
}

export function toUiError(error: unknown, context: ErrorContext): UiFeedback {
  reportClientError(error, context.operation);
  if (error instanceof ApiError) {
    return {
      kind: "error",
      message: error.message,
      requestId: error.requestId,
      retryable: context.retryable ?? isRetryableStatus(error.status),
    };
  }
  return {
    kind: "error",
    message: context.fallback,
    retryable: context.retryable ?? true,
  };
}
