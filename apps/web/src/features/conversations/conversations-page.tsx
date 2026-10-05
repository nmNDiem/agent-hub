"use client";

import {
  ArrowLeft,
  Bot,
  FileImage,
  Globe2,
  LoaderCircle,
  MessageSquareText,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { FeedbackBanner } from "@/components/feedback-banner";
import {
  api,
  type Agent,
  type ConversationDetail,
  type ConversationSummary,
} from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

function localDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBytes(value: number): string {
  return value < 1024 * 1024
    ? `${Math.ceil(value / 1024)} KiB`
    : `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

export function ConversationsPage() {
  const params = useParams<{ workspaceSlug: string; conversationPublicId?: string }>();
  const searchParams = useSearchParams();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [days, setDays] = useState<7 | 30>(() => searchParams.get("days") === "30" ? 30 : 7);
  const [agentId, setAgentId] = useState(() => searchParams.get("agent") ?? "");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail>();
  const [detailFailureId, setDetailFailureId] = useState<string>();
  const [loadingList, setLoadingList] = useState(true);
  const [busyMore, setBusyMore] = useState(false);
  const [feedback, setFeedback] = useState<UiFeedback>();
  const canView = workspace?.role === "owner" || workspace?.role === "admin";

  useEffect(() => {
    if (!workspace || !canView) return;
    let active = true;
    Promise.all([
      api.listConversations(workspace.id, {
        days,
        agentPublicId: agentId || undefined,
        limit: 20,
      }),
      api.listAgents(workspace.id),
    ]).then(([result, agentResult]) => {
      if (!active) return;
      setItems(result.items);
      setNextCursor(result.next_cursor);
      setAgents(agentResult.items);
      setFeedback(undefined);
    }).catch((caught) => {
      if (active) setFeedback(toUiError(caught, {
        operation: "conversations.load",
        fallback: "Không thể tải danh sách hội thoại.",
      }));
    }).finally(() => {
      if (active) setLoadingList(false);
    });
    return () => { active = false; };
  }, [agentId, canView, days, workspace]);

  useEffect(() => {
    if (!workspace || !canView || !params.conversationPublicId) return;
    let active = true;
    api.getConversation(workspace.id, params.conversationPublicId).then((result) => {
      if (!active) return;
      setDetail(result);
      setDetailFailureId(undefined);
    }).catch((caught) => {
      if (!active) return;
      setDetailFailureId(params.conversationPublicId);
      setFeedback(toUiError(caught, {
        operation: "conversations.detail",
        fallback: "Không thể tải nội dung hội thoại.",
      }));
    });
    return () => { active = false; };
  }, [canView, params.conversationPublicId, workspace]);

  async function loadMore() {
    if (!workspace || !nextCursor) return;
    setBusyMore(true);
    try {
      const result = await api.listConversations(workspace.id, {
        days,
        agentPublicId: agentId || undefined,
        cursor: nextCursor,
        limit: 20,
      });
      setItems((current) => [...current, ...result.items]);
      setNextCursor(result.next_cursor);
    } catch (caught) {
      setFeedback(toUiError(caught, {
        operation: "conversations.load-more",
        fallback: "Không thể tải thêm hội thoại.",
      }));
    } finally {
      setBusyMore(false);
    }
  }

  if (workspaceError) return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  if (!me || !workspace) return <main className="centered-state"><LoaderCircle className="spinner" /> Đang tải cửa hàng…</main>;
  const query = new URLSearchParams({ days: String(days) });
  if (agentId) query.set("agent", agentId);
  const listHref = `/app/${workspace.slug}/conversations?${query}`;
  const selectedDetail = detail?.conversation.public_id === params.conversationPublicId
    ? detail
    : undefined;
  const selectedDetailFailed = detailFailureId === params.conversationPublicId;

  return <AppShell user={me.user} workspace={workspace} workspaces={me.workspaces}>
    <div className="page-heading conversations-heading"><div><p className="eyebrow"><MessageSquareText size={15} /> Kênh Web · Chỉ đọc</p><h1>Hội thoại</h1><p>Xem transcript an toàn; không có trả lời, phân công, unread hay SLA.</p></div></div>
    {!canView ? <section className="empty-state"><ShieldAlert size={28} /><h2>Không có quyền truy cập</h2><p>Chỉ owner hoặc admin được xem lịch sử hội thoại.</p></section> : <>
      {feedback && <FeedbackBanner feedback={feedback} />}
      <section className={`conversation-workspace ${params.conversationPublicId ? "has-selection" : ""}`}>
        <aside className="conversation-list card-surface">
          <header><div><strong>Danh sách hội thoại</strong><span>{items.length} mục đang hiển thị</span></div><div className="conversation-filters"><label><span>Chatbot</span><select aria-label="Lọc theo chatbot" onChange={(event) => { setAgentId(event.target.value); setLoadingList(true); }} value={agentId}><option value="">Tất cả chatbot</option>{agents.map((agent) => <option key={agent.public_id} value={agent.public_id}>{agent.name}</option>)}</select></label><label><span>Thời gian</span><select aria-label="Lọc theo thời gian" onChange={(event) => { setDays(Number(event.target.value) as 7 | 30); setLoadingList(true); }} value={days}><option value={7}>7 ngày</option><option value={30}>30 ngày</option></select></label></div></header>
          {loadingList ? <div className="conversation-state"><LoaderCircle className="spinner" /> Đang tải…</div> : items.length === 0 ? <div className="conversation-state"><MessageSquareText /><strong>Không có hội thoại phù hợp</strong><span>Không hiển thị dữ liệu minh họa.</span></div> : <nav aria-label="Danh sách hội thoại"><ul>{items.map((item) => <li key={item.public_id}><Link aria-current={params.conversationPublicId === item.public_id ? "page" : undefined} href={`/app/${workspace.slug}/conversations/${item.public_id}?${query}`}><span className="conversation-avatar">?</span><span><strong>Khách ẩn danh</strong><small>{item.last_visitor_preview || "Không có nội dung xem trước"}</small><em><Globe2 size={11} /> Web · {item.agent_name}</em></span><time dateTime={item.last_message_at}>{localDate(item.last_message_at)}</time></Link></li>)}</ul></nav>}
          {nextCursor && <footer><button className="secondary-button" disabled={busyMore} onClick={() => void loadMore()} type="button">{busyMore && <LoaderCircle className="spinner" size={14} />} Tải thêm</button></footer>}
        </aside>
        <article className="conversation-detail card-surface">
          {!params.conversationPublicId ? <div className="conversation-state"><MessageSquareText /><strong>Chọn một hội thoại</strong><span>Nội dung chỉ xuất hiện sau khi bạn chọn một phiên bên trái.</span></div> : selectedDetailFailed ? <div className="conversation-state"><ShieldAlert /><strong>Không thể mở hội thoại</strong><span>Hãy thử tải lại trang hoặc chọn một hội thoại khác.</span></div> : !selectedDetail ? <div className="conversation-state"><LoaderCircle className="spinner" /> Đang tải nội dung…</div> : <>
            <header><Link className="conversation-back" href={listHref}><ArrowLeft size={16} /> Danh sách</Link><div><strong>Nội dung hội thoại</strong><span><Globe2 size={13} /> Web · {selectedDetail.conversation.agent_name}</span></div><span className="readonly-badge">Chỉ đọc</span></header>
            <div className="conversation-detail-layout">
              <div className="conversation-transcript">{selectedDetail.messages.map((message, index) => <article className={message.role} key={`${message.created_at}-${index}`}><div className="message-author">{message.role === "assistant" ? <Bot size={15} /> : <span>?</span>}<strong>{message.role === "assistant" ? selectedDetail.conversation.agent_name : "Khách ẩn danh"}</strong><time dateTime={message.created_at}>{localDate(message.created_at)}</time></div><p>{message.text || "Không có nội dung văn bản"}</p>{message.attachment && <div className="safe-attachment"><FileImage size={18} /><span><strong>Ảnh khách gửi</strong><small>{message.attachment.content_type} · {message.attachment.width}×{message.attachment.height} · {formatBytes(message.attachment.byte_size)}</small></span></div>}{message.products.length > 0 && <div className="evidence-list">{message.products.map((product) => <span key={`${product.name}-${product.sku}`}><strong>{product.name}</strong><small>{product.sku || "Không có SKU"}</small></span>)}</div>}{message.sources.length > 0 && <div className="source-list">{message.sources.map((source) => <span key={source.source_id}>{source.title}</span>)}</div>}</article>)}</div>
              <aside className="conversation-metadata"><h2>Thông tin phiên</h2><dl><div><dt>ID hội thoại</dt><dd title={selectedDetail.conversation.public_id}>{selectedDetail.conversation.public_id}</dd></div><div><dt>Bắt đầu</dt><dd>{localDate(selectedDetail.conversation.started_at)}</dd></div><div><dt>Cập nhật</dt><dd>{localDate(selectedDetail.conversation.last_message_at)}</dd></div><div><dt>Tổng tin nhắn</dt><dd>{selectedDetail.conversation.message_count}</dd></div><div><dt>Hạn lưu</dt><dd>{localDate(selectedDetail.retention_until)}</dd></div></dl></aside>
            </div>
          </>}
        </article>
      </section>
    </>}
  </AppShell>;
}
