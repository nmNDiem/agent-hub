import { afterEach, describe, expect, it, vi } from "vitest";

import { api, parsePlaygroundEventStream, type PlaygroundStreamEvent } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authenticated requests", () => {
  it("shares one refresh across concurrent unauthorized requests", async () => {
    let profileRequests = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/v1/auth/refresh") {
        return Promise.resolve(new Response("{}", { status: 200 }));
      }
      if (path === "/api/v1/me") {
        profileRequests += 1;
        if (profileRequests <= 2) {
          return Promise.resolve(new Response("{}", { status: 401 }));
        }
        return Promise.resolve(new Response(JSON.stringify({
          user: { id: "user", email: "owner@example.com", email_verified: false },
          workspaces: [],
        }), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([api.getMe(), api.getMe()]);

    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/v1/auth/refresh")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/v1/me")).toHaveLength(4);
  });

  it("does not refresh again for a stale unauthorized response", async () => {
    let profileRequests = 0;
    let resolveStaleResponse: ((response: Response) => void) | undefined;
    const staleResponse = new Promise<Response>((resolve) => {
      resolveStaleResponse = resolve;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/v1/auth/refresh") {
        return Promise.resolve(new Response("{}", { status: 200 }));
      }
      if (path === "/api/v1/me") {
        profileRequests += 1;
        if (profileRequests === 1) {
          return Promise.resolve(new Response("{}", { status: 401 }));
        }
        if (profileRequests === 2) return staleResponse;
        return Promise.resolve(new Response(JSON.stringify({
          user: { id: "user", email: "owner@example.com", email_verified: false },
          workspaces: [],
        }), { status: 200 }));
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const firstRequest = api.getMe();
    const staleRequest = api.getMe();
    await firstRequest;
    resolveStaleResponse?.(new Response("{}", { status: 401 }));
    await staleRequest;

    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/v1/auth/refresh")).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/v1/me")).toHaveLength(4);
  });
});

describe("parsePlaygroundEventStream", () => {
  it("parses SSE events across arbitrary CRLF chunk boundaries", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      "event: message.start\r",
      "\ndata: {\"message_id\":\"m1\"}\r\n\r",
      "\nevent: message.delta\r\ndata: {\"text\":\"Xin chào\"}\r\n\r\n",
      ": heartbeat\r\n\r\nevent: message.completed\r\ndata: {\"message_id\":\"m1\",\"usage\":{\"total_tokens\":3}}\r\n\r\n",
    ];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
    const events: PlaygroundStreamEvent[] = [];

    await parsePlaygroundEventStream(new Response(stream), (event) => events.push(event));

    expect(events.map((event) => event.type)).toEqual([
      "message.start",
      "message.delta",
      "message.completed",
    ]);
    expect(events[1]).toEqual({ type: "message.delta", data: { text: "Xin chào" } });
  });

  it("fails safely when the response has no readable body", async () => {
    const response = { body: null } as Response;
    await expect(parsePlaygroundEventStream(response, vi.fn())).rejects.toMatchObject({
      code: "EMPTY_STREAM",
    });
  });
});
