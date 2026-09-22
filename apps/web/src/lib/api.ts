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
type ApiErrorPayload = {
  error?: { code?: string; message?: string; details?: Record<string, unknown> };
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export type ProductSummary = {
  id: number;
  product_sku: string | null;
  name: string;
  category: string | null;
  currency: string;
  price: string | null;
  status: "active" | "archived";
  variant_count: number;
  created_at: string;
  updated_at: string;
};

export type ProductVariant = {
  id: number;
  variant_sku: string | null;
  name: string | null;
  color: string | null;
  size: string | null;
  price_override: string | null;
  effective_price: string | null;
  stock_quantity: number | null;
  status: "active" | "archived";
};

export type ProductImage = {
  id: number;
  original_filename: string;
  alt_text: string | null;
  status: "uploading" | "active" | "cleanup_pending" | "deleted";
  cleanup_attempts: number;
};

export type ProductDetail = ProductSummary & {
  description: string | null;
  product_url: string | null;
  variants: ProductVariant[];
  size_guide: { id: number; title: string; content: Record<string, unknown> } | null;
  images: ProductImage[];
};

export type ImportIssue = {
  row: number | null;
  column: string | null;
  code: string;
  message: string;
};

export type ImportPreview = {
  payload_sha256: string;
  product_count: number;
  variant_count: number;
  errors: ImportIssue[];
};

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
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !isFormData && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
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
      payload.error?.details,
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
  listProducts: (
    workspaceId: string,
    filters: { query?: string; status?: string; cursor?: string } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.query) params.set("query", filters.query);
    if (filters.status) params.set("status", filters.status);
    if (filters.cursor) params.set("cursor", filters.cursor);
    const suffix = params.size ? `?${params}` : "";
    return request<{ items: ProductSummary[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/products${suffix}`,
    );
  },
  getProduct: (workspaceId: string, productId: number) =>
    request<ProductDetail>(`/api/v1/workspaces/${workspaceId}/products/${productId}`),
  createProduct: (workspaceId: string, payload: Record<string, unknown>) =>
    request<ProductDetail>(`/api/v1/workspaces/${workspaceId}/products`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProduct: (workspaceId: string, productId: number, payload: Record<string, unknown>) =>
    request<ProductDetail>(`/api/v1/workspaces/${workspaceId}/products/${productId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  archiveProduct: (workspaceId: string, productId: number) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/products/${productId}`, {
      method: "DELETE",
    }),
  createVariant: (workspaceId: string, productId: number, payload: Record<string, unknown>) =>
    request<ProductVariant>(
      `/api/v1/workspaces/${workspaceId}/products/${productId}/variants`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  archiveVariant: (workspaceId: string, productId: number, variantId: number) =>
    request<void>(
      `/api/v1/workspaces/${workspaceId}/products/${productId}/variants/${variantId}`,
      { method: "DELETE" },
    ),
  putSizeGuide: (
    workspaceId: string,
    productId: number,
    payload: { title: string; content: Record<string, unknown> },
  ) =>
    request(`/api/v1/workspaces/${workspaceId}/products/${productId}/size-guide`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  uploadProductImage: (workspaceId: string, productId: number, form: FormData) =>
    request<ProductImage>(`/api/v1/workspaces/${workspaceId}/products/${productId}/images`, {
      method: "POST",
      body: form,
    }),
  getProductImageUrl: (workspaceId: string, productId: number, imageId: number) =>
    request<{ url: string; expires_in: number }>(
      `/api/v1/workspaces/${workspaceId}/products/${productId}/images/${imageId}/signed-url`,
    ),
  deleteProductImage: (workspaceId: string, productId: number, imageId: number) =>
    request<{ image_id: number; status: "deleted" | "cleanup_pending"; message: string }>(
      `/api/v1/workspaces/${workspaceId}/products/${productId}/images/${imageId}`,
      { method: "DELETE" },
    ),
  retryImageCleanup: (workspaceId: string, productId: number, imageId: number) =>
    request<{ image_id: number; status: "deleted" | "cleanup_pending"; message: string }>(
      `/api/v1/workspaces/${workspaceId}/products/${productId}/images/${imageId}/cleanup`,
      { method: "POST" },
    ),
  previewCatalogImport: (workspaceId: string, file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<ImportPreview>(`/api/v1/workspaces/${workspaceId}/catalog/import/preview`, {
      method: "POST",
      body: form,
    });
  },
  commitCatalogImport: (
    workspaceId: string,
    file: File,
    previewSha256: string,
    idempotencyKey: string,
  ) => {
    const form = new FormData();
    form.set("file", file);
    form.set("preview_sha256", previewSha256);
    return request<{ product_count: number; variant_count: number; replayed: boolean }>(
      `/api/v1/workspaces/${workspaceId}/catalog/import`,
      { method: "POST", body: form, headers: { "Idempotency-Key": idempotencyKey } },
    );
  },
};
