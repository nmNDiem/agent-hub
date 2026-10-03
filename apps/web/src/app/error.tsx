"use client";

import { useEffect } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { reportClientError } from "@/lib/errors";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportClientError(error, "app.render");
  }, [error]);

  return (
    <main className="center-state">
      <FeedbackBanner
        feedback={{
          kind: "error",
          message: "Màn hình này gặp sự cố. Dữ liệu của bạn không bị thay đổi.",
          requestId: error.digest,
          retryable: true,
        }}
        onRetry={reset}
      />
    </main>
  );
}
