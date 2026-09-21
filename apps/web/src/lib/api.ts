export type Workspace = {
  id: string;
  slug: string;
  display_name: string;
  timezone: string;
  role: "owner" | "admin" | "member";
  created_at: string;
};

export type CurrentUser = { id: string; email: string; email_verified: boolean };
export type Me = { user: CurrentUser; workspaces: Workspace[] };
type ApiErrorPayload = { error?: { code?: string; message?: string } };

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

function cookieValue(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix))
    ?.slice(prefix.length);
}

function isUnsafe(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

async function request<T>(path: string, init: RequestInit = {}, allowRefresh = true): Promise<T> {
  const method = init.method ?? "GET";
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  if (isUnsafe(method)) {
    const csrfToken = cookieValue("agenthub_csrf");
    if (csrfToken) headers.set("x-csrf-token", decodeURIComponent(csrfToken));
  }
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (response.status === 401 && allowRefresh && !path.startsWith("/api/v1/auth/")) {
    try {
      await request<unknown>("/api/v1/auth/refresh", { method: "POST" }, false);
      return request<T>(path, init, false);
    } catch {
      throw new ApiError(401, "UNAUTHENTICATED", "Phiên đăng nhập đã hết hạn.");
    }
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new ApiError(
      response.status,
      payload.error?.code ?? "REQUEST_FAILED",
      payload.error?.message ?? "Không thể hoàn tất yêu cầu.",
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  getMe: () => request<Me>("/api/v1/me"),
  login: (email: string, password: string) =>
    request("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) =>
    request("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  createWorkspace: (payload: { display_name: string; slug: string }) =>
    request<Workspace>("/api/v1/workspaces", { method: "POST", body: JSON.stringify(payload) }),
};
