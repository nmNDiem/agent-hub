"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { api } from "@/lib/api";

export function AppEntry() {
  const router = useRouter();

  useEffect(() => {
    api.getMe().then((me) => {
      const workspace = me.workspaces[0];
      router.replace(
        workspace
          ? `/app/${encodeURIComponent(workspace.slug)}/overview`
          : "/onboarding/create-shop",
      );
    }).catch(() => router.replace("/login?next=/app"));
  }, [router]);

  return <main className="center-state" aria-live="polite">Đang mở cửa hàng…</main>;
}
