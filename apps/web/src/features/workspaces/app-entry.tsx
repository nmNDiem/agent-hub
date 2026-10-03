"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api, ApiError } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";

export function AppEntry() {
  const router = useRouter();
  const [pageFeedback, setPageFeedback] = useState<UiFeedback>();

  useEffect(() => {
    api.getMe().then((me) => {
      const workspace = me.workspaces[0];
      router.replace(
        workspace
          ? `/app/${encodeURIComponent(workspace.slug)}/overview`
          : "/onboarding/create-shop",
      );
    }).catch((caught: unknown) => {
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace("/login?next=/app");
        return;
      }
      setPageFeedback(toUiError(caught, {
        operation: "app-entry.load-profile",
        fallback: "Không thể mở cửa hàng. Vui lòng thử lại.",
      }));
    });
  }, [router]);

  return <main className="center-state" aria-live="polite">{pageFeedback
    ? <FeedbackBanner feedback={pageFeedback} onRetry={() => location.reload()} />
    : "Đang mở cửa hàng…"}</main>;
}
