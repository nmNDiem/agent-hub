import type {
  AttachmentUpload,
  LeadCapturePayload,
  LeadCaptureResponse,
  TranscriptResponse,
  WidgetConfig,
  WidgetConversation,
  WidgetSession,
  WidgetStreamEvent,
} from "./types";

export class WidgetApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "WidgetApiError";
  }
}

async function checked(response: Response): Promise<Response> {
  if (response.ok) return response;
  const payload = await response.json().catch(() => ({})) as {
    error?: { code?: string; message?: string };
  };
  throw new WidgetApiError(
    response.status,
    payload.error?.code ?? "REQUEST_FAILED",
    payload.error?.message ?? "Không thể hoàn tất yêu cầu.",
  );
}

function bearer(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function createSession(apiBase: string, agentId: string): Promise<WidgetSession> {
  const response = await checked(await fetch(
    `${apiBase}/api/v1/widget/${encodeURIComponent(agentId)}/sessions`,
    { method: "POST", mode: "cors", credentials: "omit" },
  ));
  return response.json() as Promise<WidgetSession>;
}

export async function createConversation(
  apiBase: string,
  token: string,
): Promise<WidgetConversation> {
  const response = await checked(await fetch(`${apiBase}/api/v1/widget/conversations`, {
    method: "POST",
    mode: "cors",
    credentials: "omit",
    headers: bearer(token),
  }));
  return response.json() as Promise<WidgetConversation>;
}

export async function getTranscript(
  apiBase: string,
  token: string,
  conversationId: string,
): Promise<TranscriptResponse> {
  const response = await checked(await fetch(
    `${apiBase}/api/v1/widget/conversations/${encodeURIComponent(conversationId)}/messages`,
    { mode: "cors", credentials: "omit", headers: bearer(token) },
  ));
  return response.json() as Promise<TranscriptResponse>;
}

export async function uploadImage(
  apiBase: string,
  token: string,
  file: File,
): Promise<AttachmentUpload> {
  const body = new FormData();
  body.set("file", file);
  const response = await checked(await fetch(`${apiBase}/api/v1/widget/uploads/images`, {
    method: "POST",
    mode: "cors",
    credentials: "omit",
    headers: bearer(token),
    body,
  }));
  return response.json() as Promise<AttachmentUpload>;
}

export async function deleteImage(
  apiBase: string,
  token: string,
  attachmentId: string,
): Promise<void> {
  await checked(await fetch(
    `${apiBase}/api/v1/widget/uploads/images/${encodeURIComponent(attachmentId)}`,
    { method: "DELETE", mode: "cors", credentials: "omit", headers: bearer(token) },
  ));
}

export async function deleteConversation(
  apiBase: string,
  token: string,
  conversationId: string,
): Promise<void> {
  await checked(await fetch(
    `${apiBase}/api/v1/widget/conversations/${encodeURIComponent(conversationId)}`,
    { method: "DELETE", mode: "cors", credentials: "omit", headers: bearer(token) },
  ));
}

export async function captureLead(
  apiBase: string,
  token: string,
  conversationId: string,
  payload: LeadCapturePayload,
  idempotencyKey: string,
): Promise<LeadCaptureResponse> {
  const response = await checked(await fetch(
    `${apiBase}/api/v1/widget/conversations/${encodeURIComponent(conversationId)}/leads`,
    {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      headers: {
        ...bearer(token),
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
    },
  ));
  return response.json() as Promise<LeadCaptureResponse>;
}

export async function streamMessage(
  apiBase: string,
  token: string,
  conversationId: string,
  payload: { message: string; attachment_id?: string },
  idempotencyKey: string,
  onEvent: (event: WidgetStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await checked(await fetch(
    `${apiBase}/api/v1/widget/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      headers: {
        ...bearer(token),
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
      signal,
    },
  ));
  await parseEventStream(response, onEvent);
}

export async function fetchProductImage(
  apiBase: string,
  token: string,
  path: string,
): Promise<Blob> {
  const url = new URL(path, apiBase);
  if (url.origin !== new URL(apiBase).origin) {
    throw new WidgetApiError(400, "INVALID_IMAGE_URL", "Đường dẫn ảnh không hợp lệ.");
  }
  const response = await checked(await fetch(url, {
    mode: "cors",
    credentials: "omit",
    headers: bearer(token),
  }));
  return response.blob();
}

export async function parseEventStream(
  response: Response,
  onEvent: (event: WidgetStreamEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new WidgetApiError(502, "EMPTY_STREAM", "Chatbot không trả về dữ liệu.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function dispatch(block: string) {
    const lines = block.split("\n");
    const type = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
    const data = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!type || !data) return;
    onEvent({ type, data: JSON.parse(data) } as WidgetStreamEvent);
  }

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
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

export function validStoredSession(
  value: unknown,
): value is {
  token: string;
  expiresAt: string;
  conversationId: string;
  config: WidgetConfig;
  leadSubmitted?: boolean;
} {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.token === "string"
    && typeof item.expiresAt === "string"
    && Date.parse(item.expiresAt) > Date.now() + 30_000
    && typeof item.conversationId === "string"
    && Boolean(item.config)
    && typeof item.config === "object"
    && Boolean((item.config as Record<string, unknown>).contact)
    && (item.leadSubmitted === undefined || typeof item.leadSubmitted === "boolean");
}
