"use client";

import {
  ArrowLeft,
  Bot,
  Box,
  ExternalLink,
  LoaderCircle,
  RotateCcw,
  Save,
  Send,
  Square,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  api,
  ApiError,
  type Agent,
  type GroundedProductCard,
  type GroundedSource,
  type KnowledgeBase,
  type PlaygroundStreamEvent,
} from "@/lib/api";
import { useWorkspace } from "@/lib/use-workspace";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  state: "complete" | "streaming" | "error" | "canceled";
  products: GroundedProductCard[];
  sources: GroundedSource[];
  includeInHistory: boolean;
};

const suggestions = [
  "Gợi ý sản phẩm đang còn hàng",
  "Cửa hàng có chính sách đổi trả nào?",
  "Sản phẩm nào có nhiều tùy chọn?",
];

function messageFrom(error: unknown) {
  return error instanceof ApiError ? error.message : "Kết nối Playground bị gián đoạn.";
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

export function PlaygroundPage() {
  const params = useParams<{ workspaceSlug: string; publicAgentId: string }>();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [agent, setAgent] = useState<Agent>();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedBaseIds, setSelectedBaseIds] = useState<number[]>([]);
  const [configDraft, setConfigDraft] = useState({ name: "", greeting: "", instructions: "" });
  const [configDirty, setConfigDirty] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streamState, setStreamState] = useState<"idle" | "connecting" | "streaming" | "canceled" | "failed">("idle");
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [mobileTab, setMobileTab] = useState<"config" | "chat">("chat");
  const controller = useRef<AbortController | undefined>(undefined);
  const transcript = useRef<HTMLDivElement>(null);
  const mobileTabs = useRef<HTMLDivElement>(null);
  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";
  const streaming = streamState === "connecting" || streamState === "streaming";

  useEffect(() => {
    if (!workspace) return;
    let active = true;
    Promise.all([
      api.getAgent(workspace.id, params.publicAgentId),
      api.listKnowledgeBases(workspace.id),
      api.getAgentKnowledgeBases(workspace.id, params.publicAgentId),
    ]).then(([agentResult, basesResult, assigned]) => {
      if (!active) return;
      setAgent(agentResult);
      setKnowledgeBases(basesResult.items);
      setSelectedBaseIds(assigned.knowledge_base_ids);
      setConfigDraft({
        name: agentResult.name,
        greeting: agentResult.greeting ?? "",
        instructions: agentResult.safe_instructions ?? "",
      });
      if (agentResult.greeting) {
        setMessages([{
          id: "configured-greeting",
          role: "assistant",
          text: agentResult.greeting,
          state: "complete",
          products: [],
          sources: [],
          includeInHistory: false,
        }]);
      }
    }).catch((caught) => setError(messageFrom(caught)));
    return () => {
      active = false;
      controller.current?.abort();
    };
  }, [params.publicAgentId, workspace]);

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
      updateAssistant(id, (message) => ({ ...message, state: "error" }));
      setError(event.data.message);
      setStreamState("failed");
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    if (!workspace || !agent || streaming) return;
    const question = input.trim();
    if (!question) return;
    const history = messages
      .filter((message) => message.includeInHistory && message.state === "complete" && message.text)
      .slice(-8)
      .map(({ role, text: content }) => ({ role, content }));
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(), role: "user", text: question, state: "complete",
      products: [], sources: [], includeInHistory: true,
    };
    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId, role: "assistant", text: "", state: "streaming",
      products: [], sources: [], includeInHistory: true,
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setError(undefined);
    setStreamState("connecting");
    controller.current = new AbortController();
    try {
      await api.streamPlaygroundMessage(
        workspace.id,
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
        updateAssistant(assistantId, (message) => ({ ...message, state: "error" }));
        setError(messageFrom(caught));
        setStreamState("failed");
      }
    } finally {
      controller.current = undefined;
    }
  }

  async function saveConfiguration() {
    if (!workspace || !agent || !canWrite) return;
    setSaving(true);
    setError(undefined);
    try {
      const updated = await api.updateAgent(workspace.id, agent.public_id, {
        name: configDraft.name,
        greeting: configDraft.greeting || null,
        safe_instructions: configDraft.instructions || null,
      });
      await api.replaceAgentKnowledgeBases(workspace.id, agent.public_id, selectedBaseIds);
      setAgent(updated);
      setConfigDirty(false);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setSaving(false);
    }
  }

  function resetConversation() {
    if (messages.some((message) => message.includeInHistory) && !confirm("Xóa lịch sử thử nghiệm cục bộ?")) return;
    controller.current?.abort();
    setMessages(agent?.greeting ? [{
      id: "configured-greeting", role: "assistant", text: agent.greeting,
      state: "complete", products: [], sources: [], includeInHistory: false,
    }] : []);
    setError(undefined);
    setStreamState("idle");
  }

  function applySuggestedPrompt(suggestion: string) {
    setInput(suggestion);
    setMobileTab("chat");
    if (window.innerWidth < 1024) {
      window.requestAnimationFrame(() => {
        mobileTabs.current?.scrollIntoView({ behavior: "auto", block: "start" });
      });
    }
  }

  if (workspaceError) return <main className="center-state"><p role="alert">{workspaceError}</p></main>;
  if (!me || !workspace) return <main className="center-state" aria-live="polite">Đang tải cửa hàng…</main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="playground-heading">
        <div><Link className="back-link" href={`/app/${workspace.slug}/chatbots`}><ArrowLeft size={16} /> Chatbot</Link><h1>{agent?.name ?? "Playground"}</h1><p><span className="test-mode-badge">Đang thử bản nháp</span> Phản hồi dùng runtime và dữ liệu thật.</p></div>
        <div className="playground-heading-actions"><button className="secondary-button" onClick={resetConversation} type="button"><RotateCcw size={16} /> Làm mới hội thoại</button>{canWrite && <button className="primary-button compact-button" disabled={!configDirty || saving} onClick={() => void saveConfiguration()} type="button">{saving ? <LoaderCircle className="spinner" size={16} /> : <Save size={16} />} Lưu cấu hình</button>}</div>
      </section>
      {error && <p className="form-error playground-error" role="alert">{error}</p>}
      <div className="playground-mobile-tabs" ref={mobileTabs} role="tablist"><button aria-selected={mobileTab === "config"} onClick={() => setMobileTab("config")} role="tab" type="button">Cấu hình</button><button aria-selected={mobileTab === "chat"} onClick={() => setMobileTab("chat")} role="tab" type="button">Thử chatbot</button></div>
      <div className="playground-layout">
        <aside className={`playground-config ${mobileTab === "config" ? "mobile-active" : ""}`}>
          <div className="card-heading"><div><h2>Cấu hình thử nghiệm</h2><p>{configDirty ? "Có thay đổi chưa lưu" : "Đồng bộ với bản nháp đã lưu"}</p></div><Bot aria-hidden="true" /></div>
          {agent && <div className="playground-config-body"><fieldset disabled={!canWrite}><label>Tên chatbot<input value={configDraft.name} onChange={(event) => { setConfigDirty(true); setConfigDraft({ ...configDraft, name: event.target.value }); }} /></label><label>Lời chào<textarea rows={3} value={configDraft.greeting} onChange={(event) => { setConfigDirty(true); setConfigDraft({ ...configDraft, greeting: event.target.value }); }} /></label><label>Giọng điệu và hướng dẫn<textarea rows={5} value={configDraft.instructions} onChange={(event) => { setConfigDirty(true); setConfigDraft({ ...configDraft, instructions: event.target.value }); }} /></label></fieldset><div className="playground-source-list"><h3>Nguồn tri thức</h3><p>Runtime chỉ truy xuất tài liệu đã sẵn sàng.</p>{knowledgeBases.map((base) => <label className="source-toggle" key={base.id}><input checked={selectedBaseIds.includes(base.id)} disabled={!canWrite} onChange={() => { setConfigDirty(true); setSelectedBaseIds((current) => current.includes(base.id) ? current.filter((id) => id !== base.id) : [...current, base.id]); }} type="checkbox" /><span><strong>{base.name}</strong><small>{base.document_count} tài liệu</small></span></label>)}</div><div className="suggested-prompts"><h3>Câu hỏi gợi ý</h3>{suggestions.map((suggestion) => <button key={suggestion} onClick={() => applySuggestedPrompt(suggestion)} type="button">{suggestion}</button>)}</div></div>}
        </aside>
        <section className={`playground-chat ${mobileTab === "chat" ? "mobile-active" : ""}`}>
          <div className="chat-toolbar"><div><strong>Cuộc trò chuyện thử nghiệm</strong><small>Không lưu vào hộp thư khách hàng</small></div><span className={`stream-indicator ${streamState}`} aria-live="polite">{streamState === "connecting" ? "Đang kết nối" : streamState === "streaming" ? "Đang trả lời" : streamState === "canceled" ? "Đã dừng" : streamState === "failed" ? "Có lỗi" : "Sẵn sàng"}</span></div>
          <div className="chat-transcript" aria-live="polite" aria-busy={streaming} ref={transcript} role="log">
            {messages.length === 0 && <div className="chat-empty"><Bot size={30} /><h2>Bắt đầu thử chatbot</h2><p>Đặt câu hỏi về catalog hoặc tri thức đã gán.</p></div>}
            {messages.map((message) => <ChatBubble key={message.id} message={message} />)}
          </div>
          <form className="chat-composer" onSubmit={(event) => void sendMessage(event)}><label className="sr-only" htmlFor="playground-message">Tin nhắn thử nghiệm</label><textarea id="playground-message" maxLength={4000} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) void sendMessage(); }} placeholder="Hỏi về sản phẩm hoặc chính sách…" rows={2} value={input} /><div><small>Ctrl/⌘ + Enter để gửi</small>{streaming ? <button className="stop-button" onClick={() => controller.current?.abort()} type="button"><Square fill="currentColor" size={13} /> Dừng</button> : <button className="primary-button send-button" disabled={!input.trim() || !agent} type="submit"><Send size={16} /> Gửi</button>}</div></form>
        </section>
      </div>
    </AppShell>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  return <article className={`chat-message ${message.role}`}><span className="chat-avatar" aria-hidden="true">{message.role === "assistant" ? <Bot size={17} /> : <UserRound size={17} />}</span><div className="chat-message-body"><div className="chat-bubble">{message.text ? <p>{message.text}</p> : message.state === "streaming" ? <p className="typing-indicator"><span /><span /><span /><span className="sr-only">Đang tạo câu trả lời</span></p> : null}{message.state === "canceled" && <small>Đã dừng. Phần trả lời nhận được được giữ lại.</small>}{message.state === "error" && <small>Không thể hoàn tất câu trả lời.</small>}</div>{message.products.length > 0 && <div className="grounded-products">{message.products.map((card) => <ProductCard card={card} key={card.product_id} />)}</div>}{message.sources.length > 0 && <details className="grounded-sources"><summary>Nguồn được sử dụng ({message.sources.length})</summary><ul>{message.sources.map((source) => <li key={`${source.document_id}-${source.chunk_id}`}><strong>{source.document_title}</strong><span>{source.source_locator}</span></li>)}</ul></details>}</div></article>;
}

export function ProductCard({ card }: { card: GroundedProductCard }) {
  return <article className="grounded-product-card"><div className="grounded-product-image" aria-hidden="true"><Box size={24} /></div><div className="grounded-product-copy"><small>{card.sku ?? "Không có SKU"}</small><h3>{card.name}</h3><strong>{priceLabel(card)}</strong><span className={`inventory-label ${card.availability.in_stock_locations > 0 ? "available" : "unknown"}`}>{availabilityLabel(card)}</span>{Object.entries(card.options).length > 0 && <dl>{Object.entries(card.options).map(([name, values]) => <div key={name}><dt>{name}</dt><dd>{values.join(", ")}</dd></div>)}</dl>}{card.product_url && <a href={card.product_url} rel="noreferrer" target="_blank">Xem sản phẩm <ExternalLink size={13} /></a>}</div></article>;
}
