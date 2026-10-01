"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiError, type Me, type Workspace } from "@/lib/api";

export function useWorkspace(workspaceSlug: string) {
  const router = useRouter();
  const [me, setMe] = useState<Me>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let active = true;
    api.getMe().then((data) => {
      if (!active) return;
      if (data.workspaces.length === 0) {
        router.replace("/onboarding/create-shop");
        return;
      }
      const selected = data.workspaces.find((item) => item.slug === workspaceSlug);
      if (!selected) {
        setError("Không tìm thấy cửa hàng hoặc bạn không có quyền truy cập.");
        return;
      }
      setMe(data);
      setWorkspace(selected);
    }).catch((caught: unknown) => {
      if (!active) return;
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
      } else {
        setError("Không thể tải thông tin cửa hàng. Vui lòng thử lại.");
      }
    });
    return () => { active = false; };
  }, [router, workspaceSlug]);

  return { me, workspace, error };
}
