"use client";

import {
  Bot,
  Box,
  ExternalLink,
  RotateCcw,
  Send,
  Square,
  UserRound,
} from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  api,
  type Agent,
  type GroundedProductCard,
  type GroundedSource,
  type PlaygroundStreamEvent,
} from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  state: "complete" | "streaming" | "canceled";
  products: GroundedProductCard[];
  sources: GroundedSource[];
  includeInHistory: boolean;
};

const suggestions = [
  "Gợi ý sản phẩm đang còn hàng",
  "Cửa hàng có chính sách đổi trả nào?",
  "Sản phẩm nào có nhiều tùy chọn?",
];

function greetingMessage(agent: Agent): ChatMessage[] {
  if (!agent.greeting) return [];
  return [{
    id: `configured-greeting-${agent.public_id}`,
    role: "assistant",
    text: agent.greeting,
    state: "complete",
    products: [],
    sources: [],
    includeInHistory: false,
  }];
}

export function ChatbotPlayground({ agent, workspaceId }: { agent?: Agent; workspaceId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => agent ? greetingMessage(agent) : []);
  const [input, setInput] = useState("");
  const [streamState, setStreamState] = useState<"idle" | "connecting" | "streaming" | "canceled">("idle");
  const controller = useRef<AbortController | undefined>(undefined);
  const transcript = useRef<HTMLDivElement>(null);
  const streaming = streamState === "connecting" || streamState === "streaming";

  useEffect(() => {
    return () => controller.current?.abort();
  }, []);

  useEffect(() => {
    transcript.current?.scrollTo?.({
      top: transcript.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  function updateAssistant(id: string, update: (current: ChatMessage) => ChatMessage) {
    setMessages((current) => current.map((message) => message.id === id ? update(message) : message));
  }

  function handleStreamEvent(id: string, event: PlaygroundStreamEvent) {
    if (event.type === "message.start") setStreamState("streaming");
    if (event.type === "message.delta") {
      updateAssistant(id, (message) => ({ ...message, text: message.text + event.data.text }));
    }
    if (event.type === "product.cards") {
      updateAssistant(id, (message) => ({ ...message, products: event.data.items }));
    }
    if (event.type === "source.refs") {
      updateAssistant(id, (message) => ({ ...message, sources: event.data.items }));
    }
    if (event.type === "message.completed") {
      updateAssistant(id, (message) => ({ ...message, state: "complete" }));
      setStreamState("idle");
    }
    if (event.type === "message.error") {
      updateAssistant(id, (message) => ({
        ...message,
        text: message.text || event.data.message,
        state: "complete",
      }));
      setStreamState("idle");
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    if (!agent || streaming) return;
    const question = input.trim();
    if (!question) return;
    const history = messages
      .filter((message) => message.includeInHistory && message.state === "complete" && message.text)
      .slice(-8)
      .map(({ role, text: content }) => ({ role, content }));
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: question,
      state: "complete",
      products: [],
      sources: [],
      includeInHistory: true,
    };
    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      text: "",
      state: "streaming",
      products: [],
      sources: [],
      includeInHistory: true,
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setStreamState("connecting");
    controller.current = new AbortController();
    try {
      await api.streamPlaygroundMessage(
        workspaceId,
        agent.public_id,
        { message: question, history },
        (streamEvent) => handleStreamEvent(assistantId, streamEvent),
        controller.current.signal,
      );
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        updateAssistant(assistantId, (message) => ({ ...message, state: "canceled" }));
        setStreamState("canceled");
      } else {
        updateAssistant(assistantId, (message) => ({
          ...message,
          text: message.text || "Mình chưa thể kết nối để kiểm tra thông tin ngay lúc này. Bạn thử lại sau một chút nhé.",
          state: "complete",
        }));
        setStreamState("idle");
      }
    } finally {
      controller.current = undefined;
    }
  }

  function resetConversation() {
    if (!agent) return;
    if (messages.some((message) => message.includeInHistory)
      && !window.confirm("Xóa lịch sử thử nghiệm cục bộ?")) return;
    controller.current?.abort();
    setMessages(greetingMessage(agent));
    setStreamState("idle");
  }

  function applySuggestedPrompt(suggestion: string) {
    setInput(suggestion);
  }

  return (
    <section className="playground-chat chatbot-test-panel">
      <div className="chat-toolbar">
        <div>
          <h2><span aria-hidden="true" className="runtime-dot" /> Thử chatbot</h2>
          <small>Dùng runtime và dữ liệu thật · cấu hình đã lưu</small>
        </div>
        <div className="chat-toolbar-actions">
          <span className={`stream-indicator ${streamState}`} aria-live="polite">
            {streamState === "connecting" ? "Đang kết nối" : streamState === "streaming" ? "Đang trả lời" : streamState === "canceled" ? "Đã dừng" : "Sẵn sàng"}
          </span>
          <button aria-label="Làm mới hội thoại" className="secondary-button icon-only-button" disabled={!agent} onClick={resetConversation} type="button"><RotateCcw aria-hidden="true" size={16} /></button>
        </div>
      </div>
      <div className="chat-transcript" aria-busy={streaming} aria-live="polite" ref={transcript} role="log">
        {messages.length === 0 && <div className="chat-empty"><Bot size={30} /><h2>{agent ? "Bắt đầu thử chatbot" : "Chọn hoặc tạo chatbot"}</h2><p>{agent ? "Đặt câu hỏi về catalog hoặc tri thức đã gán." : "Bạn cần một chatbot trước khi bắt đầu thử nghiệm."}</p></div>}
        {messages.map((message) => <ChatBubble key={message.id} message={message} />)}
      </div>
      <div className="chat-prompt-zone">
        <span>Hỏi thử</span>
        <div>{suggestions.map((suggestion) => <button disabled={!agent || streaming} key={suggestion} onClick={() => applySuggestedPrompt(suggestion)} type="button">{suggestion}</button>)}</div>
      </div>
      <form className="chat-composer" onSubmit={(event) => void sendMessage(event)}>
        <label className="sr-only" htmlFor="playground-message">Tin nhắn thử nghiệm</label>
        <textarea
          disabled={!agent}
          id="playground-message"
          maxLength={4000}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) void sendMessage();
          }}
          placeholder="Hỏi về sản phẩm hoặc chính sách…"
          rows={2}
          value={input}
        />
        <div><small>Ctrl/⌘ + Enter để gửi</small>{streaming ? <button className="stop-button" onClick={() => controller.current?.abort()} type="button"><Square fill="currentColor" size={13} /> Dừng</button> : <button className="primary-button send-button" disabled={!input.trim() || !agent} type="submit"><Send size={16} /> Gửi</button>}</div>
      </form>
    </section>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  return <article className={`chat-message ${message.role}`}><span className="chat-avatar" aria-hidden="true">{message.role === "assistant" ? <Bot size={17} /> : <UserRound size={17} />}</span><div className="chat-message-body"><div className="chat-bubble">{message.text ? <p>{message.text}</p> : message.state === "streaming" ? <p className="typing-indicator"><span /><span /><span /><span className="sr-only">Đang tạo câu trả lời</span></p> : null}{message.state === "canceled" && <small>Đã dừng. Phần trả lời nhận được được giữ lại.</small>}</div>{message.products.length > 0 && <div className="grounded-products">{message.products.map((card) => <ProductCard card={card} key={card.product_id} />)}</div>}{message.sources.length > 0 && <details className="grounded-sources"><summary>Nguồn được sử dụng ({message.sources.length})</summary><ul>{message.sources.map((source) => <li key={`${source.document_id}-${source.chunk_id}`}><strong>{source.document_title}</strong><span>{source.source_locator}</span></li>)}</ul></details>}</div></article>;
}

function priceLabel(card: GroundedProductCard) {
  if (card.price.kind === "unknown" || card.price.minimum === null) return "Chưa có giá xác minh";
  const format = (value: string) => new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: card.currency,
    maximumFractionDigits: 2,
  }).format(Number(value));
  if (card.price.kind === "range" && card.price.maximum !== null) {
    return `${format(card.price.minimum)} – ${format(card.price.maximum)}`;
  }
  return format(card.price.minimum);
}

function availabilityLabel(card: GroundedProductCard) {
  const stock = card.availability;
  if (stock.in_stock_locations > 0) return `Còn hàng tại ${stock.in_stock_locations} location`;
  if (stock.unknown_locations > 0 || stock.total_locations === 0) return "Tồn kho chưa xác định";
  return "Hết hàng tại phạm vi đã chọn";
}

export function ProductCard({ card }: { card: GroundedProductCard }) {
  return <article className="grounded-product-card"><div className="grounded-product-image" aria-hidden="true"><Box size={24} /></div><div className="grounded-product-copy"><small>{card.sku ?? "Không có SKU"}</small><h3>{card.name}</h3><strong>{priceLabel(card)}</strong><span className={`inventory-label ${card.availability.in_stock_locations > 0 ? "available" : "unknown"}`}>{availabilityLabel(card)}</span>{Object.entries(card.options).length > 0 && <dl>{Object.entries(card.options).map(([name, values]) => <div key={name}><dt>{name}</dt><dd>{values.join(", ")}</dd></div>)}</dl>}{card.product_url && <a href={card.product_url} rel="noreferrer" target="_blank">Xem sản phẩm <ExternalLink size={13} /></a>}</div></article>;
}
