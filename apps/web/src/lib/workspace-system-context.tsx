"use client";

import { createContext, useContext } from "react";

import type { Me, Workspace, WorkspaceOverview } from "@/lib/api";
import type { UiFeedback } from "@/lib/errors";

export type WorkspaceSystemContextValue = {
  me: Me;
  workspace: Workspace;
  overview?: WorkspaceOverview;
  overviewError?: UiFeedback;
  overviewLoading: boolean;
  loadOverview: () => Promise<void>;
};

const WorkspaceSystemContext = createContext<WorkspaceSystemContextValue | undefined>(undefined);

export function WorkspaceSystemProvider({ children, value }: {
  children: React.ReactNode;
  value: WorkspaceSystemContextValue;
}) {
  return <WorkspaceSystemContext.Provider value={value}>{children}</WorkspaceSystemContext.Provider>;
}

export function useWorkspaceSystem(): WorkspaceSystemContextValue | undefined {
  return useContext(WorkspaceSystemContext);
}
