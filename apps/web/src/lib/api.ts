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
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
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
  options: Record<string, string>;
  price_override: string | null;
  effective_price: string | null;
  stock_quantity: number | null;
  availability: Array<{
    location_id: number;
    location_name: string;
    location_code: string | null;
    is_active: boolean;
    quantity: number | null;
    price_override: string | null;
    effective_price: string | null;
  }>;
  status: "active" | "archived";
};

export type Location = {
  id: number;
  name: string;
  code: string | null;
  type: "store" | "warehouse" | "showroom" | "service" | "online" | "other";
  address: Record<string, unknown>;
  metadata: Record<string, unknown>;
  is_active: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LocationVariant = {
  location_id: number;
  location_name: string;
  product_id: number;
  product_name: string;
  variant_id: number;
  variant_sku: string | null;
  is_active: boolean;
  base_price: string | null;
  price_override: string | null;
  effective_price: string | null;
  compare_at_price_override: string | null;
  quantity: number | null;
  updated_at: string;
};

export type CatalogCollection = {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  archived_at: string | null;
  product_ids: number[];
  created_at: string;
  updated_at: string;
};

export type ProductImage = {
  id: number;
  variant_id: number | null;
  original_filename: string | null;
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

export type CatalogImportJob = {
  id: number;
  status: "uploaded" | "analyzing" | "needs_confirmation" | "ready" | "committing" | "committed" | "failed";
  original_filename: string;
  file_type: "csv" | "xls" | "xlsx" | null;
  schema_fingerprint: string | null;
  summary: {
    products: Record<"create" | "update" | "unchanged" | "conflict", number>;
    variants: Record<"create" | "update" | "unchanged" | "conflict", number>;
    images: Record<"create" | "update" | "unchanged" | "conflict", number>;
  };
  issues: Array<{
    id: number;
    issue_type: string;
    severity: string;
    message: string;
    source_location: Record<string, unknown>;
    evidence: Record<string, unknown>;
    options: unknown[];
    status: string;
  }>;
  metadata: Record<string, unknown>;
  result: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type UniversalImportResult = {
  import_id: number;
  status: "committed";
  products_created: number;
  products_updated: number;
  products_unchanged: number;
  variants_created: number;
  variants_updated: number;
  variants_unchanged: number;
  images_created: number;
  replayed: boolean;
};

export type KnowledgeBase = {
  id: number;
  name: string;
  kind: "shop" | "faq" | "policy" | "general";
  status: "active" | "archived";
  active_embedding_profile_id: number | null;
  target_embedding_profile_id: number | null;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type IngestionStatus =
  | "uploading"
  | "awaiting_profile"
  | "queued"
  | "processing"
  | "retry_scheduled"
  | "succeeded"
  | "failed"
  | "cancelled";

export type IngestionJob = {
  id: number;
  document_id: number;
  document_version_id: number;
  target_generation_id: number | null;
  status: IngestionStatus;
  attempts: number;
  last_error_code: string | null;
  retryable: boolean;
  scheduled_at: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type KnowledgeDocument = {
  id: number;
  knowledge_base_id: number;
  title: string;
  kind: "profile" | "faq" | "policy" | "size_guidance" | "document";
  status: "active" | "deleted";
  source_kind: "manual" | "file";
  version_no: number;
  mime_type: string;
  byte_size: number;
  active_generation_id: number | null;
  ingestion_job: IngestionJob;
  created_at: string;
  updated_at: string;
};

export type Agent = {
  public_id: string;
  name: string;
  greeting: string | null;
  safe_instructions: string | null;
  default_locale: string;
  status: "draft" | "published" | "paused";
  catalog_scope: {
    location_ids: number[] | null;
    collection_ids: number[] | null;
  };
  created_at: string;
  updated_at: string;
};

export type WidgetConfig = {
  public_agent_id: string;
  display_name: string;
  greeting: string | null;
  status: "draft" | "published" | "paused";
  brand_color: string;
  launcher_position: "left" | "right";
  allowed_origins: string[];
  handoff_url: string | null;
  handoff_label: string | null;
  enabled: boolean;
  draft_differs: boolean;
  readiness: {
    has_allowed_origin: boolean;
    has_catalog_scope: boolean;
    has_knowledge: boolean;
    can_publish: boolean;
  };
  active_revision: { revision_no: number; published_at: string } | null;
  embed_snippet: string | null;
};

export type WidgetConfigUpdate = Pick<
  WidgetConfig,
  | "display_name"
  | "greeting"
  | "brand_color"
  | "launcher_position"
  | "allowed_origins"
  | "handoff_url"
  | "handoff_label"
>;

export type LeadStatus = "new" | "contacted" | "closed";

export type Lead = {
  id: number;
  conversation_public_id: string;
  agent_public_id: string;
  agent_name: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  consent_at: string;
  consent_text_version: string;
  followup_status: LeadStatus;
  retention_until: string;
  created_at: string;
  updated_at: string;
};

export type ConversationSummary = {
  public_id: string;
  channel: "web";
  agent_public_id: string;
  agent_name: string;
  started_at: string;
  last_message_at: string;
  message_count: number;
  last_visitor_preview: string | null;
};

export type ConversationDetail = {
  conversation: ConversationSummary;
  retention_until: string;
  messages: Array<{
    role: "user" | "assistant";
    text: string;
    status: "pending" | "completed" | "failed" | "cancelled";
    created_at: string;
    completed_at: string | null;
    attachment: {
      content_type: "image/jpeg" | "image/png" | "image/webp";
      width: number;
      height: number;
      byte_size: number;
      created_at: string;
    } | null;
    products: Array<{
      name: string;
      sku: string | null;
      product_url: string | null;
      price: { kind: "exact" | "range" | "unknown"; minimum: string | null; maximum: string | null };
      availability: {
        total_locations: number;
        in_stock_locations: number;
        out_of_stock_locations: number;
        unknown_locations: number;
      };
      options: Record<string, string[]>;
    }>;
    sources: Array<{ source_id: string; title: string; locator: string }>;
  }>;
};

export type UsageSummary = {
  period_started_at: string;
  period_ends_at: string;
  timezone: string;
  generated_turns: number;
  generated_turn_limit: number;
  generated_turns_remaining: number;
  generation_model_calls: number;
  vision_model_calls: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

export type Dashboard = {
  days: 7 | 30;
  timezone: string;
  total_conversations: number;
  assistant_messages: number;
  active_agents: number;
  enabled_web_channels: number;
  activity: Array<{ date: string; conversations: number }>;
  recent_conversations: ConversationSummary[];
  recent_leads: Array<{
    name: string | null;
    agent_name: string;
    followup_status: LeadStatus;
    created_at: string;
  }>;
  usage: UsageSummary;
};

export type GroundedProductCard = {
  product_id: number;
  sku: string | null;
  name: string;
  product_url: string | null;
  currency: string;
  price: { kind: "exact" | "range" | "unknown"; minimum: string | null; maximum: string | null };
  availability: {
    total_locations: number;
    in_stock_locations: number;
    out_of_stock_locations: number;
    unknown_locations: number;
  };
  options: Record<string, string[]>;
  attributes: Record<string, unknown>;
  variants: Array<{
    variant_id: number;
    sku: string | null;
    name: string | null;
    options: Record<string, string>;
    attributes: Record<string, unknown>;
    inventory_state: "in_stock" | "out_of_stock" | "unknown";
  }>;
  images: Array<{
    image_id: number;
    variant_id: number | null;
    kind: "managed" | "remote";
    alt_text: string | null;
    sort_order: number;
  }>;
};

export type GroundedSource = {
  source_id: string;
  knowledge_base_id: number;
  document_id: number;
  document_title: string;
  chunk_id: number;
  source_locator: string;
};

export type PlaygroundStreamEvent =
  | { type: "heartbeat"; data: Record<string, never> }
  | { type: "message.start"; data: { message_id: string } }
  | { type: "message.delta"; data: { text: string } }
  | { type: "product.cards"; data: { items: GroundedProductCard[] } }
  | { type: "source.refs"; data: { items: GroundedSource[] } }
  | { type: "message.completed"; data: { message_id: string; usage: Record<string, number> } }
  | { type: "message.error"; data: { code: string; message: string; retryable: boolean } };

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

let refreshPromise: Promise<void> | undefined;
let refreshGeneration = 0;

function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = authenticatedFetch(
      "/api/v1/auth/refresh",
      { method: "POST" },
      false,
    )
      .then(() => {
        refreshGeneration += 1;
      })
      .finally(() => {
        refreshPromise = undefined;
      });
  }
  return refreshPromise;
}

async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  allowRefresh = true,
): Promise<Response> {
  const requestRefreshGeneration = refreshGeneration;
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
      if (requestRefreshGeneration === refreshGeneration) {
        await refreshSession();
      }
      return authenticatedFetch(path, init, false);
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
      payload.error?.request_id ?? response.headers.get("x-request-id") ?? undefined,
    );
  }
  return response;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authenticatedFetch(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function parsePlaygroundEventStream(
  response: Response,
  onEvent: (event: PlaygroundStreamEvent) => void,
): Promise<void> {
  if (!response.body) throw new ApiError(502, "EMPTY_STREAM", "Playground không trả về dữ liệu.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function dispatch(block: string) {
    const lines = block.split("\n");
    const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
    const data = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!eventName || !data) return;
    onEvent({ type: eventName, data: JSON.parse(data) } as PlaygroundStreamEvent);
  }

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      dispatch(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  if (buffer.trim()) dispatch(buffer);
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
    filters: { query?: string; status?: string; category?: string; cursor?: string } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.query) params.set("query", filters.query);
    if (filters.status) params.set("status", filters.status);
    if (filters.category) params.set("category", filters.category);
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
  listLocations: (workspaceId: string, includeArchived = false) =>
    request<Location[]>(
      `/api/v1/workspaces/${workspaceId}/locations?include_archived=${includeArchived}`,
    ),
  createLocation: (workspaceId: string, payload: Record<string, unknown>) =>
    request<Location>(`/api/v1/workspaces/${workspaceId}/locations`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  archiveLocation: (workspaceId: string, locationId: number) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/locations/${locationId}`, {
      method: "DELETE",
    }),
  listLocationVariants: (workspaceId: string, locationId: number) =>
    request<LocationVariant[]>(
      `/api/v1/workspaces/${workspaceId}/locations/${locationId}/variants`,
    ),
  updateLocationVariant: (
    workspaceId: string,
    locationId: number,
    variantId: number,
    payload: Record<string, unknown>,
  ) => request<LocationVariant>(
    `/api/v1/workspaces/${workspaceId}/locations/${locationId}/variants/${variantId}`,
    { method: "PUT", body: JSON.stringify(payload) },
  ),
  listCollections: (workspaceId: string, includeArchived = false) =>
    request<CatalogCollection[]>(
      `/api/v1/workspaces/${workspaceId}/catalog/collections?include_archived=${includeArchived}`,
    ),
  createCollection: (workspaceId: string, payload: Record<string, unknown>) =>
    request<CatalogCollection>(`/api/v1/workspaces/${workspaceId}/catalog/collections`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  archiveCollection: (workspaceId: string, collectionId: number) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/catalog/collections/${collectionId}`, {
      method: "DELETE",
    }),
  addCollectionProduct: (workspaceId: string, collectionId: number, productId: number) =>
    request<void>(
      `/api/v1/workspaces/${workspaceId}/catalog/collections/${collectionId}/products/${productId}`,
      { method: "PUT" },
    ),
  removeCollectionProduct: (workspaceId: string, collectionId: number, productId: number) =>
    request<void>(
      `/api/v1/workspaces/${workspaceId}/catalog/collections/${collectionId}/products/${productId}`,
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
  createCatalogImport: (workspaceId: string, file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<CatalogImportJob>(`/api/v1/workspaces/${workspaceId}/catalog/imports`, {
      method: "POST",
      body: form,
    });
  },
  getCatalogImport: (workspaceId: string, importId: number) =>
    request<CatalogImportJob>(
      `/api/v1/workspaces/${workspaceId}/catalog/imports/${importId}`,
    ),
  resolveCatalogImportIssue: (
    workspaceId: string,
    importId: number,
    issueId: number,
    payload: { action: "map" | "ignore" | "select_parent"; field?: string; value?: string | number },
  ) => request<CatalogImportJob>(
    `/api/v1/workspaces/${workspaceId}/catalog/imports/${importId}/issues/${issueId}/resolve`,
    { method: "POST", body: JSON.stringify(payload) },
  ),
  commitCatalogImportJob: (workspaceId: string, importId: number, idempotencyKey: string) =>
    request<UniversalImportResult>(
      `/api/v1/workspaces/${workspaceId}/catalog/imports/${importId}/commit`,
      { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
    ),
  listKnowledgeBases: (workspaceId: string) =>
    request<{ items: KnowledgeBase[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/knowledge-bases?limit=100`,
    ),
  createKnowledgeBase: (
    workspaceId: string,
    payload: { name: string; kind: KnowledgeBase["kind"] },
  ) => request<KnowledgeBase>(`/api/v1/workspaces/${workspaceId}/knowledge-bases`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  listKnowledgeDocuments: (workspaceId: string, baseId: number) =>
    request<{ items: KnowledgeDocument[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents?limit=100`,
    ),
  createManualKnowledge: (
    workspaceId: string,
    baseId: number,
    payload: { title: string; kind: "profile" | "faq" | "policy" | "size_guidance"; content: string },
    idempotencyKey: string,
  ) => request<KnowledgeDocument>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/text`,
    { method: "POST", body: JSON.stringify(payload), headers: { "Idempotency-Key": idempotencyKey } },
  ),
  uploadKnowledgeDocument: (
    workspaceId: string,
    baseId: number,
    form: FormData,
    idempotencyKey: string,
    signal?: AbortSignal,
  ) => request<KnowledgeDocument>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents`,
    { method: "POST", body: form, signal, headers: { "Idempotency-Key": idempotencyKey } },
  ),
  deleteKnowledgeDocument: (workspaceId: string, baseId: number, documentId: number) =>
    request<void>(
      `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/${documentId}`,
      { method: "DELETE" },
    ),
  getIngestionJob: (workspaceId: string, jobId: number) =>
    request<IngestionJob>(`/api/v1/workspaces/${workspaceId}/ingestion-jobs/${jobId}`),
  retryIngestionJob: (workspaceId: string, jobId: number) =>
    request<IngestionJob>(`/api/v1/workspaces/${workspaceId}/ingestion-jobs/${jobId}/retry`, {
      method: "POST",
    }),
  listAgents: (workspaceId: string) =>
    request<{ items: Agent[] }>(`/api/v1/workspaces/${workspaceId}/agents`),
  createAgent: (workspaceId: string, payload: Pick<Agent, "name" | "default_locale">) =>
    request<Agent>(`/api/v1/workspaces/${workspaceId}/agents`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAgent: (workspaceId: string, publicAgentId: string) =>
    request<Agent>(`/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}`),
  updateAgent: (
    workspaceId: string,
    publicAgentId: string,
    payload: Partial<Pick<Agent, "name" | "greeting" | "safe_instructions" | "default_locale">>,
  ) => request<Agent>(`/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  replaceAgentCatalogScope: (
    workspaceId: string,
    publicAgentId: string,
    payload: { location_ids: number[] | null; collection_ids: number[] | null },
  ) => request<Agent>(
    `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/catalog-scope`,
    { method: "PUT", body: JSON.stringify(payload) },
  ),
  getAgentKnowledgeBases: (workspaceId: string, publicAgentId: string) =>
    request<{ public_agent_id: string; knowledge_base_ids: number[] }>(
      `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/knowledge-bases`,
    ),
  replaceAgentKnowledgeBases: (workspaceId: string, publicAgentId: string, ids: number[]) =>
    request<{ public_agent_id: string; knowledge_base_ids: number[] }>(
      `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/knowledge-bases`,
      { method: "PUT", body: JSON.stringify({ knowledge_base_ids: ids }) },
    ),
  getWidgetConfig: (workspaceId: string, publicAgentId: string) =>
    request<WidgetConfig>(
      `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/widget`,
    ),
  updateWidgetConfig: (
    workspaceId: string,
    publicAgentId: string,
    payload: WidgetConfigUpdate,
  ) => request<WidgetConfig>(
    `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/widget`,
    { method: "PUT", body: JSON.stringify(payload) },
  ),
  listLeads: (
    workspaceId: string,
    filters: { followupStatus?: LeadStatus; cursor?: string; limit?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.followupStatus) params.set("followup_status", filters.followupStatus);
    if (filters.cursor) params.set("cursor", filters.cursor);
    if (filters.limit) params.set("limit", String(filters.limit));
    const suffix = params.size ? `?${params}` : "";
    return request<{ items: Lead[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/leads${suffix}`,
    );
  },
  updateLeadStatus: (workspaceId: string, leadId: number, followupStatus: LeadStatus) =>
    request<Lead>(`/api/v1/workspaces/${workspaceId}/leads/${leadId}`, {
      method: "PATCH",
      body: JSON.stringify({ followup_status: followupStatus }),
    }),
  exportLeads: async (workspaceId: string, followupStatus?: LeadStatus) => {
    const params = new URLSearchParams();
    if (followupStatus) params.set("followup_status", followupStatus);
    const suffix = params.size ? `?${params}` : "";
    const response = await authenticatedFetch(
      `/api/v1/workspaces/${workspaceId}/leads/export.csv${suffix}`,
    );
    return response.blob();
  },
  listConversations: (
    workspaceId: string,
    filters: { cursor?: string; limit?: number; days?: 7 | 30; agentPublicId?: string } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.cursor) params.set("cursor", filters.cursor);
    if (filters.limit) params.set("limit", String(filters.limit));
    if (filters.days) params.set("days", String(filters.days));
    if (filters.agentPublicId) params.set("agent_public_id", filters.agentPublicId);
    const suffix = params.size ? `?${params}` : "";
    return request<{ items: ConversationSummary[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/conversations${suffix}`,
    );
  },
  getConversation: (workspaceId: string, conversationPublicId: string) =>
    request<ConversationDetail>(
      `/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}`,
    ),
  getDashboard: (workspaceId: string, days: 7 | 30) =>
    request<Dashboard>(`/api/v1/workspaces/${workspaceId}/dashboard?days=${days}`),
  getUsage: (workspaceId: string) =>
    request<UsageSummary>(`/api/v1/workspaces/${workspaceId}/usage`),
  publishWidget: (workspaceId: string, publicAgentId: string) =>
    request<WidgetConfig>(
      `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/publish`,
      { method: "POST" },
    ),
  pauseWidget: (workspaceId: string, publicAgentId: string) =>
    request<WidgetConfig>(
      `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/pause`,
      { method: "POST" },
    ),
  streamPlaygroundMessage: async (
    workspaceId: string,
    publicAgentId: string,
    payload: { message: string; history: Array<{ role: "user" | "assistant"; content: string }> },
    onEvent: (event: PlaygroundStreamEvent) => void,
    signal: AbortSignal,
  ) => {
    const response = await authenticatedFetch(
      `/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}/playground/messages:stream`,
      { method: "POST", body: JSON.stringify(payload), signal, headers: { Accept: "text/event-stream" } },
    );
    await parsePlaygroundEventStream(response, onEvent);
  },
};
