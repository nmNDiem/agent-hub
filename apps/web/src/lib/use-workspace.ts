"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiError, type Me, type Workspace } from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspaceSystem } from "@/lib/workspace-system-context";

export function useWorkspace(workspaceSlug: string) {
  const system = useWorkspaceSystem();
  const router = useRouter();
  const [me, setMe] = useState<Me>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [error, setError] = useState<UiFeedback>();

  useEffect(() => {
    if (system) return;
    let active = true;
    api.getMe().then((data) => {
      if (!active) return;
      if (data.workspaces.length === 0) {
        router.replace("/onboarding/create-shop");
        return;
      }
      const selected = data.workspaces.find((item) => item.slug === workspaceSlug);
      if (!selected) {
        setError(feedback("error", "Không tìm thấy cửa hàng hoặc bạn không có quyền truy cập."));
        return;
      }
      setMe(data);
      setWorkspace(selected);
    }).catch((caught: unknown) => {
      if (!active) return;
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
      } else {
        setError(toUiError(caught, {
          operation: "workspaces.load-current",
          fallback: "Không thể tải thông tin cửa hàng. Vui lòng thử lại.",
        }));
      }
    });
    return () => { active = false; };
  }, [router, system, workspaceSlug]);

  return system
    ? { me: system.me, workspace: system.workspace, error: undefined }
    : { me, workspace, error };
}
