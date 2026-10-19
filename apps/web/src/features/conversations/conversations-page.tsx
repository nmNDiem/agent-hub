"use client";

import { ArrowLeft, Bot, LoaderCircle, MessageSquareText, Send, ShieldAlert, UserRound } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type Agent, type ConversationDetail, type ConversationSummary, type InboxMember } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

const channelLabels = { web: "Website", facebook: "Facebook", zalo: "Zalo" } as const;
const statusLabels = { open: "Đang mở", pending: "Đang chờ", resolved: "Đã xử lý" } as const;
const modeLabels = { ai: "AI", human: "Nhân viên", paused: "Tạm dừng" } as const;

function localDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

export function ConversationsPage() {
  const params = useParams<{ workspaceSlug: string; conversationPublicId?: string }>();
  const searchParams = useSearchParams();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [days, setDays] = useState<7 | 30>(() => searchParams.get("days") === "30" ? 30 : 7);
  const [agentId, setAgentId] = useState(() => searchParams.get("agent") ?? "");
  const [channel, setChannel] = useState<"" | "web" | "facebook" | "zalo">("");
  const [workflowStatus, setWorkflowStatus] = useState<"" | "open" | "pending" | "resolved">("");
  const [assignedMemberId, setAssignedMemberId] = useState("");
  const [tagId, setTagId] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [members, setMembers] = useState<InboxMember[]>([]);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail>();
  const [detailFailureId, setDetailFailureId] = useState<string>();
  const [loadingList, setLoadingList] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState("");
  const [note, setNote] = useState("");
  const [tag, setTag] = useState("");
  const [feedback, setFeedback] = useState<UiFeedback>();
  const currentMember = useMemo(() => members.find((item) => item.user_id === me?.user.id), [me, members]);
  const knownTags = useMemo(() => Array.from(new Map(items.flatMap((item) => item.tags).map((item) => [item.id, item])).values()), [items]);
  const filters = useMemo(() => ({ days, agentPublicId: agentId || undefined, channel: channel || undefined, workflowStatus: workflowStatus || undefined, assignedMemberId: assignedMemberId ? Number(assignedMemberId) : undefined, tagId: tagId ? Number(tagId) : undefined, limit: 20 }), [agentId, assignedMemberId, channel, days, tagId, workflowStatus]);

  const loadList = useCallback(async () => {
    if (!workspace) return;
    setLoadingList(true);
    try {
      const result = await api.listConversations(workspace.id, filters);
      setItems(result.items); setNextCursor(result.next_cursor); setFeedback(undefined);
    } catch (caught) {
      setFeedback(toUiError(caught, { operation: "conversations.load", fallback: "Không thể tải danh sách hội thoại." }));
    } finally { setLoadingList(false); }
  }, [filters, workspace]);

  const loadDetail = useCallback(async () => {
    if (!workspace || !params.conversationPublicId) return;
    try {
      const result = await api.getConversation(workspace.id, params.conversationPublicId);
      setDetail(result); setDetailFailureId(undefined);
    } catch (caught) {
      setDetailFailureId(params.conversationPublicId);
      setFeedback(toUiError(caught, { operation: "conversations.detail", fallback: "Không thể tải nội dung hội thoại." }));
      return;
    }
    try {
      await api.markConversationRead(workspace.id, params.conversationPublicId);
      setItems((current) => current.map((item) => item.public_id === params.conversationPublicId ? { ...item, unread_count: 0 } : item));
    } catch (caught) {
      setFeedback(toUiError(caught, { operation: "conversations.mark-read", fallback: "Không thể đánh dấu hội thoại đã đọc." }));
    }
  }, [params.conversationPublicId, workspace]);

  useEffect(() => { queueMicrotask(() => void loadList()); }, [loadList]);
  useEffect(() => {
    if (!workspace) return;
    let active = true;
    Promise.all([api.listAgents(workspace.id), api.listInboxMembers(workspace.id)]).then(([agentResult, memberResult]) => {
      if (active) { setAgents(agentResult.items); setMembers(memberResult.items); }
    }).catch((caught) => { if (active) setFeedback(toUiError(caught, { operation: "inbox.options", fallback: "Không thể tải tùy chọn inbox." })); });
    return () => { active = false; };
  }, [workspace]);
  useEffect(() => { queueMicrotask(() => void loadDetail()); }, [loadDetail]);

  async function mutate(action: () => Promise<void>) {
    setBusy(true);
    try { await action(); await loadList(); await loadDetail(); }
    catch (caught) { setFeedback(toUiError(caught, { operation: "inbox.update", fallback: "Không thể cập nhật hội thoại." })); }
    finally { setBusy(false); }
  }

  async function loadMore() {
    if (!workspace || !nextCursor) return;
    setBusy(true);
    try {
      const result = await api.listConversations(workspace.id, { ...filters, cursor: nextCursor });
      setItems((current) => [...current, ...result.items]); setNextCursor(result.next_cursor);
    } catch (caught) { setFeedback(toUiError(caught, { operation: "conversations.load-more", fallback: "Không thể tải thêm hội thoại." })); }
    finally { setBusy(false); }
  }

  if (workspaceError) return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  if (!me || !workspace) return <main className="centered-state"><LoaderCircle className="spinner" /> Đang tải cửa hàng…</main>;
  const query = new URLSearchParams({ days: String(days) }); if (agentId) query.set("agent", agentId);
  const selected = detail?.conversation.public_id === params.conversationPublicId ? detail : undefined;

  return <>
    <div className="page-heading"><h1>Inbox</h1></div>
    {feedback && <FeedbackBanner feedback={feedback} />}
    <section className={`conversation-workspace ${params.conversationPublicId ? "has-selection" : ""}`}>
      <aside className="conversation-list card-surface"><header><div><strong>Hội thoại</strong><span>{items.length} mục</span></div><div className="conversation-filters inbox-filters">
        <label><span>Kênh</span><select aria-label="Lọc theo kênh" onChange={(event) => setChannel(event.target.value as typeof channel)} value={channel}><option value="">Tất cả</option><option value="web">Website</option><option value="facebook">Facebook</option><option value="zalo">Zalo</option></select></label>
        <label><span>Trạng thái</span><select aria-label="Lọc theo trạng thái" onChange={(event) => setWorkflowStatus(event.target.value as typeof workflowStatus)} value={workflowStatus}><option value="">Tất cả</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label><span>Chatbot</span><select aria-label="Lọc theo chatbot" onChange={(event) => setAgentId(event.target.value)} value={agentId}><option value="">Tất cả</option>{agents.map((agent) => <option key={agent.public_id} value={agent.public_id}>{agent.name}</option>)}</select></label>
        <label><span>Thời gian</span><select aria-label="Lọc theo thời gian" onChange={(event) => setDays(Number(event.target.value) as 7 | 30)} value={days}><option value={7}>7 ngày</option><option value={30}>30 ngày</option></select></label>
        <label><span>Phụ trách</span><select aria-label="Lọc theo người phụ trách" onChange={(event) => setAssignedMemberId(event.target.value)} value={assignedMemberId}><option value="">Tất cả</option>{members.map((member) => <option key={member.id} value={member.id}>{member.email}</option>)}</select></label>
        <label><span>Thẻ</span><select aria-label="Lọc theo thẻ" onChange={(event) => setTagId(event.target.value)} value={tagId}><option value="">Tất cả</option>{knownTags.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </div></header>
      {loadingList ? <div className="conversation-state"><LoaderCircle className="spinner" /> Đang tải…</div> : items.length === 0 ? <div className="conversation-state"><MessageSquareText /><strong>Không có hội thoại phù hợp</strong></div> : <nav aria-label="Danh sách hội thoại"><ul>{items.map((item) => <li key={item.public_id}><Link aria-current={params.conversationPublicId === item.public_id ? "page" : undefined} href={`/app/${workspace.slug}/conversations/${item.public_id}?${query}`}><span className="conversation-avatar">{item.unread_count || "?"}</span><span><strong>Khách hàng</strong><small>{item.last_visitor_preview || "Không có nội dung xem trước"}</small><em>{channelLabels[item.channel]} · {item.agent_name} · {statusLabels[item.workflow_status]}</em></span><time>{localDate(item.last_message_at)}</time></Link></li>)}</ul></nav>}
      {nextCursor && <footer><button className="secondary-button" disabled={busy} onClick={() => void loadMore()} type="button">Tải thêm</button></footer>}</aside>
      <article className="conversation-detail card-surface">{!params.conversationPublicId ? <div className="conversation-state"><MessageSquareText /><strong>Chọn một hội thoại</strong></div> : detailFailureId === params.conversationPublicId ? <div className="conversation-state"><ShieldAlert /><strong>Không thể mở hội thoại</strong><span>Hãy thử tải lại trang hoặc chọn một hội thoại khác.</span></div> : !selected ? <div className="conversation-state"><LoaderCircle className="spinner" /> Đang tải nội dung…</div> : <>
        <header><Link className="conversation-back" href={`/app/${workspace.slug}/conversations?${query}`}><ArrowLeft size={16} /> Danh sách</Link><div><strong>{selected.conversation.contact_public_id ? <Link href={`/app/${workspace.slug}/contacts/${selected.conversation.contact_public_id}`}>Khách hàng</Link> : "Khách hàng"}</strong><span>{channelLabels[selected.conversation.channel]} · {selected.conversation.agent_name}</span></div><button className="secondary-button" disabled={busy} onClick={() => void mutate(() => api.updateConversationState(workspace.id, selected.conversation.public_id, { state_version: selected.conversation.state_version, handling_mode: selected.conversation.handling_mode === "human" ? "ai" : "human", ...(selected.conversation.handling_mode !== "human" && currentMember ? { assigned_member_id: currentMember.id } : {}) }))} type="button">{selected.conversation.handling_mode === "human" ? "Bật lại AI" : "Tiếp quản"}</button></header>
        <div className="conversation-detail-layout"><div className="conversation-main"><div className="conversation-transcript">{selected.messages.map((message) => <article className={message.role === "user" ? "visitor" : message.role} key={message.id}><div className="message-author">{message.role === "assistant" ? <Bot size={15} /> : message.role === "human" ? <UserRound size={15} /> : <span>?</span>}<strong>{message.role === "assistant" ? selected.conversation.agent_name : message.role === "human" ? "Nhân viên" : "Khách hàng"}</strong><time>{localDate(message.created_at)}</time></div><p>{message.text || "Không có nội dung văn bản"}</p>{message.delivery && <small className={`delivery-state ${message.delivery.state}`}>Gửi: {message.delivery.state}{message.delivery.safe_error_code ? ` · ${message.delivery.safe_error_code}` : ""}</small>}</article>)}</div>
          <form className="inbox-composer" onSubmit={(event) => { event.preventDefault(); const text = reply.trim(); if (text) void mutate(async () => { await api.replyToConversation(workspace.id, selected.conversation.public_id, text, crypto.randomUUID()); setReply(""); }); }}><textarea aria-label="Nội dung trả lời" disabled={busy || selected.conversation.handling_mode !== "human"} maxLength={4000} onChange={(event) => setReply(event.target.value)} placeholder={selected.conversation.handling_mode === "human" ? "Nhập câu trả lời…" : "Tiếp quản để trả lời"} value={reply} /><button className="primary-button" disabled={busy || selected.conversation.handling_mode !== "human" || !reply.trim()} type="submit"><Send size={15} /> Gửi</button></form></div>
          <aside className="conversation-metadata"><h2>Vận hành</h2><label>Phụ trách<select disabled={busy || workspace.role === "member"} onChange={(event) => void mutate(() => api.updateConversationState(workspace.id, selected.conversation.public_id, { state_version: selected.conversation.state_version, ...(event.target.value ? { assigned_member_id: Number(event.target.value) } : { clear_assignment: true }) }))} value={selected.conversation.assigned_member_id ?? ""}><option value="">Chưa phân công</option>{members.map((member) => <option key={member.id} value={member.id}>{member.email}</option>)}</select></label><label>Trạng thái<select disabled={busy} onChange={(event) => void mutate(() => api.updateConversationState(workspace.id, selected.conversation.public_id, { state_version: selected.conversation.state_version, workflow_status: event.target.value as keyof typeof statusLabels }))} value={selected.conversation.workflow_status}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><dl><div><dt>Chế độ</dt><dd>{modeLabels[selected.conversation.handling_mode]}</dd></div><div><dt>Hạn lưu</dt><dd>{localDate(selected.retention_until)}</dd></div></dl>
          <h2>Thẻ</h2><div className="tag-list">{selected.conversation.tags.map((item) => <span key={item.id}>{item.name}</span>)}</div><form className="metadata-form" onSubmit={(event) => { event.preventDefault(); if (tag.trim()) void mutate(async () => { await api.addConversationTag(workspace.id, selected.conversation.public_id, tag); setTag(""); }); }}><input aria-label="Thẻ mới" maxLength={48} onChange={(event) => setTag(event.target.value)} value={tag} /><button disabled={busy}>Thêm</button></form>
          <h2>Ghi chú</h2><div className="note-list">{selected.notes.map((item) => <article key={item.id}><strong>{item.author_email}</strong><p>{item.body}</p><time>{localDate(item.created_at)}</time></article>)}</div><form className="metadata-form" onSubmit={(event) => { event.preventDefault(); if (note.trim()) void mutate(async () => { await api.addConversationNote(workspace.id, selected.conversation.public_id, note); setNote(""); }); }}><textarea aria-label="Ghi chú nội bộ" maxLength={2000} onChange={(event) => setNote(event.target.value)} value={note} /><button disabled={busy}>Lưu ghi chú</button></form></aside></div>
      </>}</article>
    </section>
  </>;
}
