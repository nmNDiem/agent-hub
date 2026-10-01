import { describe, expect, it, vi } from "vitest";

import { parsePlaygroundEventStream, type PlaygroundStreamEvent } from "./api";

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
