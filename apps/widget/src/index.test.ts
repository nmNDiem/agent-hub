// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getWidgetPackageInfo, mountWidget } from "./index";

const agentId = "0199a105-6d50-7abc-8def-1234567890ab";
const apiBase = "https://chat.example.com";
const token = "private-widget-session-token";

function jsonResponse(payload: object, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function sessionResponse(imageInput = false) {
  return {
    access_token: token,
    expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    config: {
      display_name: "Trợ lý ND Shop",
      greeting: "Xin chào! Mình có thể giúp bạn tìm sản phẩm phù hợp.",
      brand_color: "#0F8F87",
      launcher_position: "right" as const,
      capabilities: { image_input: imageInput },
      contact: {
        handoff_url: "https://shop.example.com/contact",
        handoff_label: "Liên hệ trực tiếp",
        consent_text: "Tôi đồng ý để cửa hàng liên hệ lại.",
        consent_text_version: "vi-VN:contact-v1:30d",
        lead_retention_days: 30,
      },
    },
  };
}

function conversationResponse() {
  return {
    public_id: "0199a105-6d50-7abc-8def-1234567890ac",
    status: "open",
    retention_until: new Date(Date.now() + 3_600_000).toISOString(),
  };
}

function sseResponse(): Response {
  const body = [
    'event: message.start\ndata: {"message_id":"0199a105-6d50-7abc-8def-1234567890ad"}\n\n',
    'event: message.delta\ndata: {"text":"Mình đã tìm thấy sản phẩm phù hợp."}\n\n',
    'event: message.completed\ndata: {"message_id":"0199a105-6d50-7abc-8def-1234567890ad","usage":{"total_tokens":10}}\n\n',
  ].join("");
  return new Response(body, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("AgentHub website widget", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    document.body.replaceChildren();
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("reports a functional package and renders an isolated accessible launcher", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(sessionResponse()))
      .mockResolvedValueOnce(jsonResponse(conversationResponse(), 201));
    vi.stubGlobal("fetch", fetchMock);
    const target = document.createElement("div");
    document.body.append(target);

    mountWidget({ agentId, apiBase, target });
    expect(getWidgetPackageInfo()).toEqual({ status: "functional", functional: true });
    expect(target.shadowRoot).not.toBeNull();
    expect(document.querySelector(".ah-panel")).toBeNull();
    expect(target.style.getPropertyValue("position")).toBe("fixed");
    expect(target.style.getPropertyPriority("position")).toBe("important");
    expect(target.style.getPropertyValue("z-index")).toBe("2147483000");

    await vi.waitFor(() => {
      expect(target.shadowRoot?.querySelector(".ah-header-copy strong")?.textContent)
        .toBe("Trợ lý ND Shop");
    });
    expect(target.style.getPropertyValue("--ah-brand")).toBe("#0F8F87");
    expect(target.style.getPropertyPriority("--ah-brand")).toBe("important");
    const launcher = target.shadowRoot!.querySelector<HTMLButtonElement>(".ah-launcher")!;
    launcher.click();
    expect(launcher.getAttribute("aria-expanded")).toBe("true");
    expect(target.shadowRoot!.querySelector(".ah-panel")?.hasAttribute("hidden")).toBe(false);
    expect(target.shadowRoot!.textContent).toContain("Xin chào!");
    expect(target.shadowRoot!.innerHTML).not.toContain(token);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${apiBase}/api/v1/widget/${agentId}/sessions`,
      expect.objectContaining({ method: "POST", credentials: "omit" }),
    );
  });

  it("streams a message without sending workspace scope or client history", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(sessionResponse()))
      .mockResolvedValueOnce(jsonResponse(conversationResponse(), 201))
      .mockResolvedValueOnce(sseResponse());
    vi.stubGlobal("fetch", fetchMock);
    const target = document.createElement("div");
    document.body.append(target);
    mountWidget({ agentId, apiBase, target });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const textarea = target.shadowRoot!.querySelector<HTMLTextAreaElement>("textarea")!;
    textarea.value = "Có áo linen màu xanh không?";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    target.shadowRoot!.querySelector<HTMLFormElement>("form")!
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() => {
      expect(target.shadowRoot!.textContent).toContain("Mình đã tìm thấy sản phẩm phù hợp.");
    });
    const request = fetchMock.mock.calls[2];
    expect(request?.[0]).toContain("/messages");
    const init = request?.[1] as RequestInit;
    expect(new Headers(init.headers).get("authorization")).toBe(`Bearer ${token}`);
    expect(new Headers(init.headers).get("idempotency-key")).toBeTruthy();
    const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(payload).toEqual({ message: "Có áo linen màu xanh không?" });
    expect(payload).not.toHaveProperty("workspace_id");
    expect(payload).not.toHaveProperty("history");
  });

  it("restores only a valid session-scoped transcript from sessionStorage", async () => {
    const expiresAt = new Date(Date.now() + 3_600_000).toISOString();
    sessionStorage.setItem(`agenthub:widget:${apiBase}:${agentId}`, JSON.stringify({
      token,
      expiresAt,
      conversationId: conversationResponse().public_id,
      config: sessionResponse().config,
    }));
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({
      waiting_human: false,
      items: [{
        sequence_no: 1,
        role: "user",
        text: "Tin nhắn đã lưu",
        status: "completed",
        response_id: null,
        product_cards: [],
        sources: [],
        created_at: new Date().toISOString(),
      }],
    }));
    vi.stubGlobal("fetch", fetchMock);
    const target = document.createElement("div");
    document.body.append(target);
    mountWidget({ agentId, apiBase, target });

    await vi.waitFor(() => expect(target.shadowRoot!.textContent).toContain("Tin nhắn đã lưu"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/messages");
    expect(target.shadowRoot!.innerHTML).not.toContain(token);
    expect(target.outerHTML).not.toContain(token);
  });

  it("restores handoff synchronization and stops after AI resumes", async () => {
    sessionStorage.setItem(`agenthub:widget:${apiBase}:${agentId}`, JSON.stringify({
      token,
      expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
      conversationId: conversationResponse().public_id,
      config: sessionResponse().config,
    }));
    const humanReply = {
      sequence_no: 2,
      role: "assistant",
      text: "Nhân viên đã phản hồi.",
      status: "completed",
      response_id: null,
      product_cards: [],
      sources: [],
      created_at: new Date().toISOString(),
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [], waiting_human: true }))
      .mockResolvedValueOnce(jsonResponse({ items: [humanReply], waiting_human: false }));
    vi.stubGlobal("fetch", fetchMock);
    const target = document.createElement("div");
    document.body.append(target);

    mountWidget({ agentId, apiBase, target });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(
      target.shadowRoot!.querySelector(".ah-transcript")!.getAttribute("aria-busy"),
    ).toBe("false"));
    target.shadowRoot!.querySelector<HTMLButtonElement>(".ah-launcher")!.click();

    await vi.waitFor(() => expect(target.shadowRoot!.textContent).toContain(humanReply.text));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("uploads a validated image handle and sends it without exposing file bytes", async () => {
    const NativeURL = URL;
    class TestURL extends NativeURL {
      static createObjectURL = vi.fn(() => "blob:local-preview");
      static revokeObjectURL = vi.fn();
    }
    vi.stubGlobal("URL", TestURL);
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(sessionResponse(true)))
      .mockResolvedValueOnce(jsonResponse(conversationResponse(), 201))
      .mockResolvedValueOnce(jsonResponse({
        attachment_id: "0199a105-6d50-7abc-8def-1234567890ae",
        content_type: "image/jpeg",
        width: 24,
        height: 18,
        expires_at: new Date(Date.now() + 1_800_000).toISOString(),
      }, 201))
      .mockResolvedValueOnce(sseResponse());
    vi.stubGlobal("fetch", fetchMock);
    const target = document.createElement("div");
    document.body.append(target);
    mountWidget({ agentId, apiBase, target });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], "look.jpg", {
      type: "image/jpeg",
    });
    const input = target.shadowRoot!.querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, "files", { configurable: true, value: [file] });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    await vi.waitFor(() => expect(target.shadowRoot!.textContent).toContain("look.jpg"));

    target.shadowRoot!.querySelector<HTMLFormElement>("form")!
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const uploadInit = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect(uploadInit.body).toBeInstanceOf(FormData);
    expect(String(uploadInit.body)).not.toContain("private-widget-session-token");
    const messageInit = fetchMock.mock.calls[3]?.[1] as RequestInit;
    expect(JSON.parse(String(messageInit.body))).toEqual({
      message: "Tìm sản phẩm tương tự trong cửa hàng",
      attachment_id: "0199a105-6d50-7abc-8def-1234567890ae",
    });
  });

  it("captures contact only after explicit consent without exposing workspace scope", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(sessionResponse()))
      .mockResolvedValueOnce(jsonResponse(conversationResponse(), 201))
      .mockResolvedValueOnce(jsonResponse({
        status: "received",
        followup_status: "new",
        retention_until: new Date(Date.now() + 30 * 86_400_000).toISOString(),
      }, 201));
    vi.stubGlobal("fetch", fetchMock);
    const target = document.createElement("div");
    document.body.append(target);
    mountWidget({ agentId, apiBase, target });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const root = target.shadowRoot!;
    expect(root.textContent).toContain("Nhờ shop liên hệ");
    root.querySelector<HTMLButtonElement>(".ah-contact-toggle")!.click();
    const form = root.querySelector<HTMLFormElement>(".ah-contact-form")!;
    const email = form.querySelector<HTMLInputElement>('input[name="email"]')!;
    email.value = "customer@example.com";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(root.textContent).toContain("Bạn cần đồng ý");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    form.querySelector<HTMLInputElement>('input[name="consent"]')!.checked = true;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(root.textContent).toContain("Shop đã nhận yêu cầu"));
    const request = fetchMock.mock.calls[2];
    expect(String(request?.[0])).toContain("/leads");
    const init = request?.[1] as RequestInit;
    expect(new Headers(init.headers).get("authorization")).toBe(`Bearer ${token}`);
    expect(new Headers(init.headers).get("idempotency-key")).toBeTruthy();
    const payload = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(payload).toEqual({
      name: null,
      email: "customer@example.com",
      phone: null,
      consent_given: true,
      consent_text_version: "vi-VN:contact-v1:30d",
    });
    expect(payload).not.toHaveProperty("workspace_id");
  });

  it("fails closed for invalid public configuration", () => {
    expect(() => mountWidget({ agentId: "not-an-id", apiBase })).toThrow(/UUIDv7/);
    expect(() => mountWidget({ agentId, apiBase: "javascript:alert(1)" })).toThrow(/HTTP/);
  });
});
