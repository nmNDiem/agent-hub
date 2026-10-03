import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Agent, GroundedProductCard, PlaygroundStreamEvent } from "@/lib/api";

import { ChatbotPlayground } from "./chatbot-playground";

const mocks = vi.hoisted(() => ({
  streamPlaygroundMessage: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, streamPlaygroundMessage: mocks.streamPlaygroundMessage } };
});

const workspaceId = "01992f3c-4436-7000-8000-000000000001";
const agent: Agent = {
  public_id: "01992f3c-4436-7000-8000-000000000010",
  name: "Trợ lý thời trang",
  greeting: null,
  safe_instructions: "Trả lời ngắn gọn.",
  default_locale: "vi",
  status: "draft",
  catalog_scope: { location_ids: null, collection_ids: null },
  created_at: "2026-09-30T00:00:00Z",
  updated_at: "2026-09-30T00:00:00Z",
};

const productOnly: GroundedProductCard = {
  product_id: 1,
  sku: "BASIC-1",
  name: "Túi cơ bản",
  product_url: null,
  currency: "VND",
  price: { kind: "exact", minimum: "150000.00", maximum: "150000.00" },
  availability: { total_locations: 0, in_stock_locations: 0, out_of_stock_locations: 0, unknown_locations: 0 },
  options: {},
  attributes: {},
  variants: [],
  images: [],
};

const multiOption: GroundedProductCard = {
  ...productOnly,
  product_id: 2,
  sku: "LINEN-2",
  name: "Áo linen",
  price: { kind: "range", minimum: "250000.00", maximum: "290000.00" },
  availability: { total_locations: 2, in_stock_locations: 1, out_of_stock_locations: 0, unknown_locations: 1 },
  options: { Màu: ["Xanh", "Trắng"], "Chất liệu": ["Linen"] },
};

describe("ChatbotPlayground", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders grounded product-only, multi-option and source events", async () => {
    mocks.streamPlaygroundMessage.mockImplementation(async (
      _workspaceId: string,
      _agentId: string,
      _payload: unknown,
      onEvent: (event: PlaygroundStreamEvent) => void,
    ) => {
      onEvent({ type: "message.start", data: { message_id: "message-1" } });
      onEvent({ type: "message.delta", data: { text: "Mình tìm thấy hai sản phẩm." } });
      onEvent({ type: "product.cards", data: { items: [productOnly, multiOption] } });
      onEvent({ type: "source.refs", data: { items: [{ source_id: "source_1", knowledge_base_id: 3, document_id: 9, document_title: "Chính sách", chunk_id: 12, source_locator: "Trang 1" }] } });
      onEvent({ type: "message.completed", data: { message_id: "message-1", usage: { total_tokens: 12 } } });
    });
    render(<ChatbotPlayground agent={agent} workspaceId={workspaceId} />);

    fireEvent.change(screen.getByLabelText("Tin nhắn thử nghiệm"), { target: { value: "Gợi ý sản phẩm" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));

    expect(await screen.findByText("Túi cơ bản")).toBeInTheDocument();
    expect(screen.getByText("Áo linen")).toBeInTheDocument();
    expect(screen.getByText("Xanh, Trắng")).toBeInTheDocument();
    expect(screen.getByText("Tồn kho chưa xác định")).toBeInTheDocument();
    expect(screen.getByText("Nguồn được sử dụng (1)")).toBeInTheDocument();
  });

  it("aborts an active stream and retains the partial answer", async () => {
    mocks.streamPlaygroundMessage.mockImplementation(async (
      _workspaceId: string,
      _agentId: string,
      _payload: unknown,
      onEvent: (event: PlaygroundStreamEvent) => void,
      signal: AbortSignal,
    ) => {
      onEvent({ type: "message.start", data: { message_id: "message-2" } });
      onEvent({ type: "message.delta", data: { text: "Phần trả lời đã nhận" } });
      await new Promise<void>((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });
    render(<ChatbotPlayground agent={agent} workspaceId={workspaceId} />);
    fireEvent.change(screen.getByLabelText("Tin nhắn thử nghiệm"), { target: { value: "Kiểm tra dừng" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));

    expect(await screen.findByText("Phần trả lời đã nhận")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dừng" }));
    expect(await screen.findByText("Đã dừng. Phần trả lời nhận được được giữ lại.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Đã dừng")).toBeInTheDocument());
  });

  it("renders runtime and connection failures as natural assistant replies", async () => {
    mocks.streamPlaygroundMessage
      .mockImplementationOnce(async (
        _workspaceId: string,
        _agentId: string,
        _payload: unknown,
        onEvent: (event: PlaygroundStreamEvent) => void,
      ) => {
        onEvent({ type: "message.start", data: { message_id: "message-3" } });
        onEvent({
          type: "message.error",
          data: {
            code: "GENERATION_UNAVAILABLE",
            message: "Mình chưa kiểm tra được thông tin này. Bạn thử lại sau nhé.",
            retryable: true,
          },
        });
      })
      .mockRejectedValueOnce(new Error("network details must stay internal"));
    render(<ChatbotPlayground agent={agent} workspaceId={workspaceId} />);

    fireEvent.change(screen.getByLabelText("Tin nhắn thử nghiệm"), { target: { value: "Kiểm tra runtime" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(await screen.findAllByText("Mình chưa kiểm tra được thông tin này. Bạn thử lại sau nhé.")).toHaveLength(2);
    expect(screen.getByRole("alert")).toHaveTextContent("Mình chưa kiểm tra được thông tin này.");

    fireEvent.change(screen.getByLabelText("Tin nhắn thử nghiệm"), { target: { value: "Kiểm tra kết nối" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(await screen.findByText(/Mình chưa thể kết nối để kiểm tra thông tin/)).toBeInTheDocument();
    expect(screen.queryByText(/network details/)).not.toBeInTheDocument();
    expect(screen.getByText("Sẵn sàng")).toBeInTheDocument();
  });
});
