"use client";

import { LoaderCircle } from "lucide-react";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { SystemShell } from "@/components/system-shell";
import { api, type WorkspaceOverview } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";
import { WorkspaceSystemProvider } from "@/lib/workspace-system-context";

export function WorkspaceSystemBoundary({ children, workspaceSlug }: {
  children: React.ReactNode;
  workspaceSlug: string;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { me, workspace, error } = useWorkspace(workspaceSlug);
  const [overview, setOverview] = useState<WorkspaceOverview>();
  const [overviewError, setOverviewError] = useState<UiFeedback>();
  const [overviewLoading, setOverviewLoading] = useState(true);
  const requestedDays: 7 | 30 = pathname.endsWith("/overview") && searchParams.get("days") === "30" ? 30 : 7;

  const loadOverview = useCallback(async (days: 7 | 30 = requestedDays): Promise<void> => {
    if (!workspace) return;
    setOverviewLoading(true);
    try {
      const result = await api.getWorkspaceOverview(workspace.id, days);
      setOverview(result);
      setOverviewError(undefined);
    } catch (caught) {
      setOverviewError(toUiError(caught, {
        operation: "workspace.system.load",
        fallback: "Không thể tải cấu trúc hệ thống của workspace.",
      }));
    } finally {
      setOverviewLoading(false);
    }
  }, [requestedDays, workspace]);

  useEffect(() => { void loadOverview(requestedDays); }, [loadOverview, requestedDays]);

  const context = useMemo(() => me && workspace ? {
    me,
    workspace,
    overview,
    overviewError,
    overviewLoading,
    loadOverview,
  } : undefined, [loadOverview, me, overview, overviewError, overviewLoading, workspace]);

  if (error) return <main className="centered-state"><FeedbackBanner feedback={error} /></main>;
  if (!context) return <main className="centered-state"><LoaderCircle aria-hidden="true" className="spinner" /> Đang tải workspace…</main>;

  return <WorkspaceSystemProvider value={context}>
    <SystemShell overview={overview} user={context.me.user} workspace={context.workspace} workspaces={context.me.workspaces}>{children}</SystemShell>
  </WorkspaceSystemProvider>;
}
