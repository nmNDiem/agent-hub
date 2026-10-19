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
  recovery_state:
    | "in_progress"
    | "ready"
    | "retryable_failure"
    | "permanent_failure"
    | "attempts_exhausted"
    | "lease_expired"
    | "projection_drift"
    | "cancelled";
  active_generation_changed: boolean;
};

export type KnowledgeFreshness = "unknown" | "current" | "due_soon" | "overdue";

export type KnowledgeDocument = {
  id: number;
  knowledge_base_id: number;
  title: string;
  kind: "profile" | "faq" | "policy" | "size_guidance" | "document";
  status: "active" | "deleted";
  source_kind: "manual" | "file";
  latest_version_id: number;
  version_no: number;
  mime_type: string;
  byte_size: number;
  active_generation_id: number | null;
  active_version_no: number | null;
  reviewed_at: string | null;
  review_due_at: string | null;
  reviewed_by_user_id: string | null;
  freshness_state: KnowledgeFreshness;
  ingestion_job: IngestionJob;
  active_generation_changed: boolean;
  created_at: string;
  updated_at: string;
};

export type KnowledgeVersion = {
  id: number;
  version_no: number;
  source_kind: "manual" | "file";
  mime_type: string;
  byte_size: number;
  content_sha256: string;
  created_by_user_id: string;
  created_at: string;
  reviewed_at: string | null;
  review_due_at: string | null;
  reviewed_by_user_id: string | null;
  freshness_state: KnowledgeFreshness;
  generation_id: number | null;
  generation_status: "building" | "ready" | "failed" | "revoked" | null;
  generation_failure_code: string | null;
  is_active: boolean;
  ingestion_job: IngestionJob | null;
};

export type KnowledgeDiagnostic = {
  status: "completed" | "dependency_unavailable";
  target_type: "knowledge_bases" | "agent";
  resolved_knowledge_base_ids: number[];
  active_sources: Array<{
    knowledge_base_id: number;
    document_id: number;
    document_title: string;
    version_id: number;
    version_no: number;
    generation_id: number;
  }>;
  hits: Array<{
    rank: number;
    knowledge_base_id: number;
    document_id: number;
    document_title: string;
    chunk_id: number;
    source_locator: string;
    embedding_profile_id: number;
    similarity_score: number;
    snippet: string;
  }>;
  raw_hit_count: number;
  discarded_hit_count: number;
  reason_codes: string[];
};

export type AgentIcon =
  | "message-circle"
  | "bot"
  | "headphones"
  | "sparkles"
  | "shopping-bag"
  | "calendar-days"
  | "briefcase-business"
  | "heart-handshake";

export type Agent = {
  public_id: string;
  name: string;
  icon: AgentIcon;
  color: string;
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

export type FacebookConnection = {
  id: number;
  provider: "facebook";
  display_name: string;
  external_account_id: string;
  lifecycle_state: "active" | "revoked";
  health_state:
    | "unknown"
    | "healthy"
    | "permission_expired"
    | "reauth_required"
    | "webhook_subscription_failure"
    | "delivery_unknown";
  agent_public_id: string;
  agent_name: string;
  latest_queue_state:
    | "queued"
    | "running"
    | "completed"
    | "failed_retryable"
    | "failed_terminal"
    | "suppressed"
    | null;
  latest_delivery_state:
    | "queued"
    | "sending"
    | "accepted"
    | "delivered"
    | "failed_retryable"
    | "failed_terminal"
    | null;
  latest_safe_error_code: string | null;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ZaloConnection = {
  id: number;
  provider: "zalo";
  display_name: string;
  external_account_id: string;
  lifecycle_state: "active" | "revoked";
  health_state:
    | "unknown"
    | "healthy"
    | "permission_expired"
    | "reauth_required"
    | "webhook_subscription_failure"
    | "delivery_unknown";
  webhook_configured: boolean;
  agent_public_id: string;
  agent_name: string;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
};

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
  contact_public_id: string | null;
  channel: "web" | "facebook" | "zalo";
  agent_public_id: string;
  agent_name: string;
  started_at: string;
  last_message_at: string;
  message_count: number;
  last_visitor_preview: string | null;
  workflow_status: "open" | "pending" | "resolved";
  handling_mode: "ai" | "human" | "paused";
  state_version: number;
  assigned_member_id: number | null;
  assigned_member_email: string | null;
  unread_count: number;
  tags: Array<{ id: number; name: string }>;
};

export type ContactSummary = {
  public_id: string;
  display_name: string | null;
  lifecycle_state: "active" | "expired" | "merged";
  state_version: number;
  assigned_member_id: number | null;
  assigned_member_email: string | null;
  channels: Array<"website" | "facebook" | "zalo">;
  tags: Array<{ id: number; name: string }>;
  retention_until: string;
  updated_at: string;
};

export type ContactDetail = {
  contact: ContactSummary;
  canonical_public_id: string | null;
  identities: Array<{
    id: number;
    provider: "website" | "facebook" | "zalo";
    identity_type: "email" | "phone" | "channel";
    value: string | null;
    verification_state: "consented" | "provider_asserted";
    consent_at: string | null;
    consent_text_version: string | null;
    retention_until: string;
  }>;
  notes: Array<{ id: number; author_member_id: number; author_email: string; body: string; created_at: string }>;
  timeline: Array<{
    key: string;
    kind: "conversation" | "lead" | "note" | "state" | "merge";
    occurred_at: string;
    title: string;
    detail: string | null;
    conversation_public_id: string | null;
    lead_id: number | null;
  }>;
  duplicate_candidates: Array<{
    public_id: string;
    display_name: string | null;
    matching_identity_types: Array<"email" | "phone">;
  }>;
  active_merges: Array<{
    id: number;
    source_public_id: string;
    target_public_id: string;
    reason: string;
    created_at: string;
  }>;
};

export type InboxMember = {
  id: number;
  user_id: string;
  email: string;
  role: "owner" | "admin" | "member";
};

export type ConversationDetail = {
  conversation: ConversationSummary;
  retention_until: string;
  messages: Array<{
    id: number;
    role: "user" | "assistant" | "human";
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
    delivery: {
      state: "queued" | "sending" | "accepted" | "delivered" | "failed_retryable" | "failed_terminal";
      attempt_count: number;
      max_attempts: number;
      next_attempt_at: string;
      safe_error_code: string | null;
    } | null;
  }>;
  notes: Array<{ id: number; author_member_id: number; author_email: string; body: string; created_at: string }>;
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

export type OverviewDependencyState = "ready" | "partial" | "stale" | "unavailable";
export type OverviewAttentionReason =
  | "knowledge_stale"
  | "knowledge_failed"
  | "website_not_ready"
  | "channel_disconnected"
  | "channel_degraded"
  | "handover_pending";

export type WorkspaceOverview = {
  workspace_id: string;
  workspace_slug: string;
  workspace_name: string;
  role: Workspace["role"];
  generated_at: string;
  days: 7 | 30;
  window_started_at: string;
  capabilities: {
    catalog: { available: boolean; can_setup: boolean };
  };
  dependencies: Record<
    "agents" | "knowledge" | "channels" | "conversations" | "catalog",
    { state: OverviewDependencyState; reason: string | null }
  >;
  agent_total: number;
  agents_truncated: boolean;
  agents: Array<{
    public_id: string;
    name: string;
    icon: AgentIcon;
    color: string;
    lifecycle_state: "draft" | "published" | "paused";
    updated_at: string;
    active_revision: { id: number; revision_no: number; published_at: string } | null;
    knowledge: {
      total: number;
      truncated: boolean;
      items: Array<{
        id: number;
        name: string;
        kind: "shop" | "faq" | "policy" | "general";
        state: "ready" | "stale" | "failed";
      }>;
    };
    channels: Record<"web" | "facebook" | "zalo", {
      total: number;
      truncated: boolean;
      items: Array<{
        id: number;
        provider: "web" | "facebook" | "zalo";
        display_name: string;
        lifecycle_state: "active" | "revoked";
        health_state:
          | "unknown"
          | "healthy"
          | "permission_expired"
          | "reauth_required"
          | "webhook_subscription_failure"
          | "delivery_unknown";
        enabled: boolean;
        active_revision_id: number | null;
      }>;
    }>;
    catalog_scope: {
      available: boolean;
      locations: {
        total: number;
        truncated: boolean;
        all_accessible: boolean;
        items: Array<{ id: number; name: string }>;
      };
      collections: {
        total: number;
        truncated: boolean;
        all_accessible: boolean;
        items: Array<{ id: number; name: string }>;
      };
    };
    website_readiness: {
      configured: boolean;
      has_allowed_origin: boolean;
      has_knowledge: boolean;
      has_catalog_scope: boolean;
      can_publish: boolean;
    };
    conversations: { total: number; open: number; pending: number; human_handling: number };
    attention_reasons: OverviewAttentionReason[];
  }>;
};

export type AnalyticsDeliveryOutcomes = {
  accepted: number;
  delivered: number;
  failed_retryable: number;
  failed_terminal: number;
};

export type AnalyticsBreakdown = {
  key: string;
  label: string;
  conversations: number;
  inbound_messages: number;
  completed_replies: number;
  delivery: AnalyticsDeliveryOutcomes | null;
};

export type OperationalAnalytics = {
  days: 7 | 30;
  timezone: string;
  period_started_at: string;
  period_ends_at: string;
  channel: "web" | "facebook" | "zalo" | null;
  agent_public_id: string | null;
  summary: { conversations: number; inbound_messages: number; completed_replies: number; failed_replies: number };
  first_response: { average_seconds: number | null; sample_count: number };
  human_response: { average_seconds: number | null; sample_count: number };
  resolution: { ai_only_resolved: number; human_handled_resolved: number; unresolved: number; handoffs: number };
  lead_conversion: { converted_conversations: number; eligible_conversations: number; rate: number | null };
  activity: Array<{ date: string; conversations: number; inbound_messages: number; completed_replies: number }>;
  by_channel: AnalyticsBreakdown[];
  by_agent: AnalyticsBreakdown[];
  product_interest: Array<{ product_id: number; product_name: string; impressions: number; conversations: number }>;
  agent_options: Array<{ public_id: string; name: string }>;
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
  replaceManualKnowledgeDocument: (
    workspaceId: string,
    baseId: number,
    documentId: number,
    content: string,
    idempotencyKey: string,
  ) => request<KnowledgeDocument>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/${documentId}/versions/text`,
    { method: "POST", body: JSON.stringify({ content }), headers: { "Idempotency-Key": idempotencyKey } },
  ),
  replaceFileKnowledgeDocument: (
    workspaceId: string,
    baseId: number,
    documentId: number,
    form: FormData,
    idempotencyKey: string,
  ) => request<KnowledgeDocument>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/${documentId}/versions`,
    { method: "POST", body: form, headers: { "Idempotency-Key": idempotencyKey } },
  ),
  listKnowledgeVersions: (workspaceId: string, baseId: number, documentId: number) =>
    request<{ items: KnowledgeVersion[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/${documentId}/versions?limit=50`,
    ),
  reviewKnowledgeVersion: (
    workspaceId: string,
    baseId: number,
    documentId: number,
    versionId: number,
    reviewDueAt: string | null,
  ) => request<KnowledgeVersion>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/${documentId}/versions/${versionId}/review`,
    { method: "PATCH", body: JSON.stringify({ review_due_at: reviewDueAt }) },
  ),
  rebuildKnowledgeVersion: (
    workspaceId: string,
    baseId: number,
    documentId: number,
    versionId: number,
    reason: string,
    idempotencyKey: string,
  ) => request<IngestionJob>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases/${baseId}/documents/${documentId}/versions/${versionId}/rebuild`,
    { method: "POST", body: JSON.stringify({ reason }), headers: { "Idempotency-Key": idempotencyKey } },
  ),
  retryIngestionJob: (workspaceId: string, jobId: number, reason = "Operator requested retry") =>
    request<IngestionJob>(`/api/v1/workspaces/${workspaceId}/ingestion-jobs/${jobId}/retry`, {
      method: "POST",
      body: JSON.stringify({ reason }),
      headers: { "Idempotency-Key": crypto.randomUUID() },
    }),
  runKnowledgeDiagnostic: (
    workspaceId: string,
    payload: { query: string; limit: number } & (
      | { knowledge_base_ids: number[]; agent_public_id?: never }
      | { agent_public_id: string; knowledge_base_ids?: never }
    ),
  ) => request<KnowledgeDiagnostic>(`/api/v1/workspaces/${workspaceId}/knowledge/diagnostics`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  listAgents: (workspaceId: string) =>
    request<{ items: Agent[] }>(`/api/v1/workspaces/${workspaceId}/agents`),
  createAgent: (
    workspaceId: string,
    payload: Pick<Agent, "name" | "default_locale"> & Partial<Pick<Agent, "icon" | "color">>,
  ) =>
    request<Agent>(`/api/v1/workspaces/${workspaceId}/agents`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAgent: (workspaceId: string, publicAgentId: string) =>
    request<Agent>(`/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}`),
  updateAgent: (
    workspaceId: string,
    publicAgentId: string,
    payload: Partial<Pick<
      Agent,
      "name" | "icon" | "color" | "greeting" | "safe_instructions" | "default_locale"
    >>,
  ) => request<Agent>(`/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  deleteAgent: (workspaceId: string, publicAgentId: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/agents/${publicAgentId}`, {
      method: "DELETE",
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
  listContacts: (
    workspaceId: string,
    filters: { cursor?: string; limit?: number; query?: string; assignedMemberId?: number; tagId?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.cursor) params.set("cursor", filters.cursor);
    if (filters.limit) params.set("limit", String(filters.limit));
    if (filters.query) params.set("query", filters.query);
    if (filters.assignedMemberId) params.set("assigned_member_id", String(filters.assignedMemberId));
    if (filters.tagId) params.set("tag_id", String(filters.tagId));
    const suffix = params.size ? `?${params}` : "";
    return request<{ items: ContactSummary[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/contacts${suffix}`,
    );
  },
  getContact: (workspaceId: string, contactPublicId: string) =>
    request<ContactDetail>(`/api/v1/workspaces/${workspaceId}/contacts/${contactPublicId}`),
  updateContact: (
    workspaceId: string,
    contactPublicId: string,
    payload: { state_version: number; display_name?: string | null; update_display_name?: boolean; assigned_member_id?: number; clear_assignment?: boolean },
  ) => request<void>(`/api/v1/workspaces/${workspaceId}/contacts/${contactPublicId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  addContactNote: (workspaceId: string, contactPublicId: string, body: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/contacts/${contactPublicId}/notes`, { method: "POST", body: JSON.stringify({ body }) }),
  addContactTag: (workspaceId: string, contactPublicId: string, name: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/contacts/${contactPublicId}/tags`, { method: "POST", body: JSON.stringify({ name }) }),
  mergeContacts: (workspaceId: string, targetPublicId: string, payload: { source_public_id: string; source_state_version: number; target_state_version: number; reason: string }) =>
    request<{ merge_id: number }>(`/api/v1/workspaces/${workspaceId}/contacts/${targetPublicId}/merges`, { method: "POST", body: JSON.stringify(payload) }),
  reverseContactMerge: (workspaceId: string, targetPublicId: string, mergeId: number) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/contacts/${targetPublicId}/merges/${mergeId}/reverse`, { method: "POST" }),
  exportContacts: async (workspaceId: string) => {
    const response = await authenticatedFetch(`/api/v1/workspaces/${workspaceId}/contacts/export.csv`);
    return response.blob();
  },
  listConversations: (
    workspaceId: string,
    filters: { cursor?: string; limit?: number; days?: 7 | 30; agentPublicId?: string; channel?: "web" | "facebook" | "zalo"; workflowStatus?: "open" | "pending" | "resolved"; assignedMemberId?: number; tagId?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.cursor) params.set("cursor", filters.cursor);
    if (filters.limit) params.set("limit", String(filters.limit));
    if (filters.days) params.set("days", String(filters.days));
    if (filters.agentPublicId) params.set("agent_public_id", filters.agentPublicId);
    if (filters.channel) params.set("channel", filters.channel);
    if (filters.workflowStatus) params.set("workflow_status", filters.workflowStatus);
    if (filters.assignedMemberId) params.set("assigned_member_id", String(filters.assignedMemberId));
    if (filters.tagId) params.set("tag_id", String(filters.tagId));
    const suffix = params.size ? `?${params}` : "";
    return request<{ items: ConversationSummary[]; next_cursor: string | null }>(
      `/api/v1/workspaces/${workspaceId}/conversations${suffix}`,
    );
  },
  getConversation: (workspaceId: string, conversationPublicId: string) =>
    request<ConversationDetail>(
      `/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}`,
    ),
  listInboxMembers: (workspaceId: string) =>
    request<{ items: InboxMember[] }>(`/api/v1/workspaces/${workspaceId}/inbox/members`),
  markConversationRead: (workspaceId: string, conversationPublicId: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}/read`, { method: "POST" }),
  updateConversationState: (workspaceId: string, conversationPublicId: string, payload: { state_version: number; workflow_status?: "open" | "pending" | "resolved"; handling_mode?: "ai" | "human" | "paused"; assigned_member_id?: number; clear_assignment?: boolean }) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}/state`, { method: "PATCH", body: JSON.stringify(payload) }),
  addConversationNote: (workspaceId: string, conversationPublicId: string, body: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}/notes`, { method: "POST", body: JSON.stringify({ body }) }),
  addConversationTag: (workspaceId: string, conversationPublicId: string, name: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}/tags`, { method: "POST", body: JSON.stringify({ name }) }),
  replyToConversation: (workspaceId: string, conversationPublicId: string, text: string, idempotencyKey: string) =>
    request<void>(`/api/v1/workspaces/${workspaceId}/conversations/${conversationPublicId}/replies`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ text }) }),
  getDashboard: (workspaceId: string, days: 7 | 30) =>
    request<Dashboard>(`/api/v1/workspaces/${workspaceId}/dashboard?days=${days}`),
  getWorkspaceOverview: (workspaceId: string, days: 7 | 30 = 7) =>
    request<WorkspaceOverview>(`/api/v1/workspaces/${workspaceId}/overview?days=${days}`),
  getAnalytics: (
    workspaceId: string,
    filters: { days: 7 | 30; channel?: "web" | "facebook" | "zalo"; agentPublicId?: string },
  ) => {
    const params = new URLSearchParams({ days: String(filters.days) });
    if (filters.channel) params.set("channel", filters.channel);
    if (filters.agentPublicId) params.set("agent_public_id", filters.agentPublicId);
    return request<OperationalAnalytics>(`/api/v1/workspaces/${workspaceId}/analytics?${params}`);
  },
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
  listFacebookConnections: (workspaceId: string) =>
    request<{ items: FacebookConnection[] }>(
      `/api/v1/workspaces/${workspaceId}/channels/facebook`,
    ),
  connectFacebook: (
    workspaceId: string,
    payload: { agent_public_id: string; page_access_token: string },
  ) => request<FacebookConnection>(
    `/api/v1/workspaces/${workspaceId}/channels/facebook`,
    { method: "POST", body: JSON.stringify(payload) },
  ),
  verifyFacebookConnection: (workspaceId: string, connectionId: number) =>
    request<FacebookConnection>(
      `/api/v1/workspaces/${workspaceId}/channels/facebook/${connectionId}/health`,
      { method: "POST" },
    ),
  reauthorizeFacebookConnection: (
    workspaceId: string,
    connectionId: number,
    pageAccessToken: string,
  ) => request<FacebookConnection>(
    `/api/v1/workspaces/${workspaceId}/channels/facebook/${connectionId}/reauthorize`,
    { method: "POST", body: JSON.stringify({ page_access_token: pageAccessToken }) },
  ),
  revokeFacebookConnection: (workspaceId: string, connectionId: number) =>
    request<void>(
      `/api/v1/workspaces/${workspaceId}/channels/facebook/${connectionId}`,
      { method: "DELETE" },
    ),
  listZaloConnections: (workspaceId: string) =>
    request<{ items: ZaloConnection[] }>(
      `/api/v1/workspaces/${workspaceId}/channels/zalo`,
    ),
  startZaloOAuth: (
    workspaceId: string,
    payload: { agent_public_id: string; reauthorize_connection_id?: number },
  ) => request<{ authorization_url: string; expires_at: string }>(
    `/api/v1/workspaces/${workspaceId}/channels/zalo/oauth/start`,
    { method: "POST", body: JSON.stringify(payload) },
  ),
  setZaloWebhookSecret: (workspaceId: string, connectionId: number, webhookSecret: string) =>
    request<ZaloConnection>(
      `/api/v1/workspaces/${workspaceId}/channels/zalo/${connectionId}/webhook-secret`,
      { method: "PUT", body: JSON.stringify({ webhook_secret: webhookSecret }) },
    ),
  verifyZaloConnection: (workspaceId: string, connectionId: number) =>
    request<ZaloConnection>(
      `/api/v1/workspaces/${workspaceId}/channels/zalo/${connectionId}/health`,
      { method: "POST" },
    ),
  revokeZaloConnection: (workspaceId: string, connectionId: number) =>
    request<void>(
      `/api/v1/workspaces/${workspaceId}/channels/zalo/${connectionId}`,
      { method: "DELETE" },
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
