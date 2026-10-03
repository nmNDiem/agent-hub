import { AlertCircle, CheckCircle2, Info, RefreshCw, TriangleAlert } from "lucide-react";

import type { UiFeedback } from "@/lib/errors";

type FeedbackBannerProps = {
  feedback: UiFeedback;
  onRetry?: () => void;
  retryLabel?: string;
};

const icons = {
  error: AlertCircle,
  warning: TriangleAlert,
  success: CheckCircle2,
  info: Info,
};

export function FeedbackBanner({ feedback, onRetry, retryLabel = "Thử lại" }: FeedbackBannerProps) {
  const Icon = icons[feedback.kind];
  const canRetry = feedback.retryable && onRetry;
  return (
    <section
      aria-live={feedback.kind === "error" ? "assertive" : "polite"}
      className={`feedback-banner feedback-${feedback.kind}`}
      role={feedback.kind === "error" ? "alert" : "status"}
    >
      <Icon aria-hidden="true" className="feedback-icon" size={18} />
      <div className="feedback-copy">
        <p>{feedback.message}</p>
        {feedback.requestId && <small>Mã hỗ trợ: <code>{feedback.requestId}</code></small>}
      </div>
      {canRetry && (
        <button className="feedback-retry" onClick={onRetry} type="button">
          <RefreshCw aria-hidden="true" size={15} /> {retryLabel}
        </button>
      )}
    </section>
  );
}
