"use client";

import {
  ArrowLeft,
  Download,
  LoaderCircle,
  Merge,
  MessageSquareText,
  RotateCcw,
  Search,
  ShieldAlert,
  UserRound,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import {
  api,
  type ContactDetail,
  type ContactSummary,
  type InboxMember,
  type LeadStatus,
} from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

const providerLabels = { website: "Website", facebook: "Facebook", zalo: "Zalo" } as const;
const identityLabels = { email: "Email", phone: "Điện thoại", channel: "Danh tính kênh" } as const;
const leadLabels: Record<LeadStatus, string> = {
  new: "Mới",
  contacted: "Đã liên hệ",
  closed: "Đã đóng",
};

function localDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function initials(name: string | null): string {
  return name?.trim().charAt(0).toUpperCase() || "?";
}

export function ContactsPage() {
  const params = useParams<{ workspaceSlug: string; contactPublicId?: string }>();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [items, setItems] = useState<ContactSummary[]>([]);
  const [members, setMembers] = useState<InboxMember[]>([]);
  const [detail, setDetail] = useState<ContactDetail>();
  const [detailFailureId, setDetailFailureId] = useState<string>();
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [busy, setBusy] = useState(false);
  const [searchDraft, setSearchDraft] = useState("");
  const [query, setQuery] = useState("");
  const [assignedMemberId, setAssignedMemberId] = useState("");
  const [tagId, setTagId] = useState("");
  const [note, setNote] = useState("");
  const [tag, setTag] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [mergeSource, setMergeSource] = useState("");
  const [mergeReason, setMergeReason] = useState("");
  const [feedback, setFeedback] = useState<UiFeedback>();
  const currentMember = useMemo(
    () => members.find((member) => member.user_id === me?.user.id),
    [me, members],
  );
  const knownTags = useMemo(
    () => Array.from(new Map(items.flatMap((item) => item.tags).map((item) => [item.id, item])).values()),
    [items],
  );
  const filters = useMemo(() => ({
    query: query || undefined,
    assignedMemberId: assignedMemberId ? Number(assignedMemberId) : undefined,
    tagId: tagId ? Number(tagId) : undefined,
    limit: 20,
  }), [assignedMemberId, query, tagId]);

  const loadList = useCallback(async () => {
    if (!workspace) return;
    setLoadingList(true);
    try {
      const result = await api.listContacts(workspace.id, filters);
      setItems(result.items);
      setNextCursor(result.next_cursor);
      setFeedback(undefined);
    } catch (caught) {
      setFeedback(toUiError(caught, {
        operation: "contacts.load",
        fallback: "Không thể tải danh sách khách hàng.",
      }));
    } finally {
      setLoadingList(false);
    }
  }, [filters, workspace]);

  const loadDetail = useCallback(async () => {
    if (!workspace || !params.contactPublicId) return;
    try {
      const result = await api.getContact(workspace.id, params.contactPublicId);
      setDetail(result);
      setDisplayName(result.contact.display_name ?? "");
      setDetailFailureId(undefined);
    } catch (caught) {
      setDetailFailureId(params.contactPublicId);
      setFeedback(toUiError(caught, {
        operation: "contacts.detail",
        fallback: "Không thể tải hồ sơ khách hàng.",
      }));
    }
  }, [params.contactPublicId, workspace]);

  useEffect(() => { queueMicrotask(() => void loadList()); }, [loadList]);
  useEffect(() => { queueMicrotask(() => void loadDetail()); }, [loadDetail]);
  useEffect(() => {
    if (!workspace) return;
    let active = true;
    api.listInboxMembers(workspace.id)
      .then((result) => { if (active) setMembers(result.items); })
      .catch((caught) => {
        if (active) setFeedback(toUiError(caught, {
          operation: "contacts.members",
          fallback: "Không thể tải danh sách người phụ trách.",
        }));
      });
    return () => { active = false; };
  }, [workspace]);

  async function mutate(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
      await loadList();
      await loadDetail();
      setFeedback(undefined);
    } catch (caught) {
      setFeedback(toUiError(caught, {
        operation: "contacts.update",
        fallback: "Không thể cập nhật hồ sơ khách hàng.",
      }));
    } finally {
      setBusy(false);
    }
  }

  async function loadMore() {
    if (!workspace || !nextCursor) return;
    setBusy(true);
    try {
      const result = await api.listContacts(workspace.id, { ...filters, cursor: nextCursor });
      setItems((current) => [...current, ...result.items]);
      setNextCursor(result.next_cursor);
    } catch (caught) {
      setFeedback(toUiError(caught, {
        operation: "contacts.load-more",
        fallback: "Không thể tải thêm khách hàng.",
      }));
    } finally {
      setBusy(false);
    }
  }

  async function exportContacts() {
    if (!workspace) return;
    setBusy(true);
    try {
      const blob = await api.exportContacts(workspace.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "agenthub-contacts.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setFeedback(toUiError(caught, {
        operation: "contacts.export",
        fallback: "Không thể xuất dữ liệu khách hàng.",
      }));
    } finally {
      setBusy(false);
    }
  }

  if (workspaceError) {
    return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  }
  if (!me || !workspace) {
    return <main className="centered-state"><LoaderCircle className="spinner" /> Đang tải cửa hàng…</main>;
  }
  const selected = detail?.contact.public_id === params.contactPublicId ? detail : undefined;
  const canAdmin = workspace.role === "owner" || workspace.role === "admin";
  const canOperate = canAdmin
    || (selected?.contact.assigned_member_id !== null
      && selected?.contact.assigned_member_id === currentMember?.id);

  return <>
    <div className="page-heading contacts-heading">
      <div>
        <p className="eyebrow"><Users size={15} /> Website · Facebook · Zalo</p>
        <h1>Khách hàng</h1>
        <p>Một hồ sơ consent-aware và timeline thống nhất cho mọi kênh liên hệ.</p>
      </div>
      {canAdmin && <button className="secondary-button" disabled={busy} onClick={() => void exportContacts()} type="button"><Download size={16} /> Xuất CSV</button>}
    </div>
    {feedback && <FeedbackBanner feedback={feedback} />}
    <section className={`conversation-workspace contact-workspace ${params.contactPublicId ? "has-selection" : ""}`}>
      <aside className="conversation-list card-surface">
        <header>
          <div><strong>Danh bạ</strong><span>{items.length} hồ sơ</span></div>
          <form className="contact-search" onSubmit={(event) => { event.preventDefault(); setQuery(searchDraft.trim()); }}>
            <input aria-label="Tìm khách hàng" maxLength={120} onChange={(event) => setSearchDraft(event.target.value)} placeholder="Tên, email hoặc số điện thoại" value={searchDraft} />
            <button aria-label="Tìm kiếm" type="submit"><Search size={16} /></button>
          </form>
          <div className="conversation-filters">
            <label><span>Phụ trách</span><select aria-label="Lọc theo người phụ trách" onChange={(event) => setAssignedMemberId(event.target.value)} value={assignedMemberId}><option value="">Tất cả</option>{members.map((member) => <option key={member.id} value={member.id}>{member.email}</option>)}</select></label>
            <label><span>Thẻ</span><select aria-label="Lọc theo thẻ" onChange={(event) => setTagId(event.target.value)} value={tagId}><option value="">Tất cả</option>{knownTags.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          </div>
        </header>
        {loadingList ? <div className="conversation-state"><LoaderCircle className="spinner" /> Đang tải…</div> : items.length === 0 ? <div className="conversation-state"><Users /><strong>Không có khách hàng phù hợp</strong><span>Contact chỉ được tạo từ tương tác hoặc consent hợp lệ.</span></div> : <nav aria-label="Danh sách khách hàng"><ul>{items.map((item) => <li key={item.public_id}><Link aria-current={params.contactPublicId === item.public_id ? "page" : undefined} href={`/app/${workspace.slug}/contacts/${item.public_id}`}><span className="conversation-avatar">{initials(item.display_name)}</span><span><strong>{item.display_name || "Khách chưa cung cấp tên"}</strong><small>{item.assigned_member_email || "Chưa phân công"}</small><em>{item.channels.map((channel) => providerLabels[channel]).join(" · ") || "Chưa có kênh"}</em></span><time>{localDate(item.updated_at)}</time></Link></li>)}</ul></nav>}
        {nextCursor && <footer><button className="secondary-button" disabled={busy} onClick={() => void loadMore()} type="button">Tải thêm</button></footer>}
      </aside>
      <article className="conversation-detail card-surface">
        {!params.contactPublicId ? <div className="conversation-state"><UserRound /><strong>Chọn một khách hàng</strong><span>Hồ sơ và timeline sẽ xuất hiện tại đây.</span></div> : detailFailureId === params.contactPublicId ? <div className="conversation-state"><ShieldAlert /><strong>Không thể mở hồ sơ</strong><span>Hãy thử tải lại hoặc chọn hồ sơ khác.</span></div> : !selected ? <div className="conversation-state"><LoaderCircle className="spinner" /> Đang tải hồ sơ…</div> : <>
          <header>
            <Link className="conversation-back" href={`/app/${workspace.slug}/contacts`}><ArrowLeft size={16} /> Danh sách</Link>
            <div><strong>{selected.contact.display_name || "Khách chưa cung cấp tên"}</strong><span>{selected.contact.channels.map((channel) => providerLabels[channel]).join(" · ")} · lưu đến {localDate(selected.contact.retention_until)}</span></div>
            {!canAdmin && selected.contact.assigned_member_id === null && currentMember && <button className="secondary-button" disabled={busy} onClick={() => void mutate(() => api.updateContact(workspace.id, selected.contact.public_id, { state_version: selected.contact.state_version, assigned_member_id: currentMember.id }))} type="button">Nhận xử lý</button>}
          </header>
          <div className="conversation-detail-layout contact-detail-layout">
            <div className="conversation-main contact-main">
              {selected.canonical_public_id && <div className="contact-merge-notice"><Merge size={16} /> Hồ sơ này đã được hợp nhất. <Link href={`/app/${workspace.slug}/contacts/${selected.canonical_public_id}`}>Mở hồ sơ chính</Link></div>}
              <section className="contact-profile-section">
                <h2>Danh tính và consent</h2>
                <div className="identity-list">{selected.identities.map((identity) => <article key={identity.id}><strong>{providerLabels[identity.provider]} · {identityLabels[identity.identity_type]}</strong><span>{identity.value || "ID kênh được bảo vệ"}</span><small>{identity.verification_state === "consented" ? `Consent ${identity.consent_text_version ?? "đã ghi nhận"}` : "Được provider xác nhận trong hội thoại"}</small></article>)}</div>
              </section>
              <section className="contact-profile-section contact-timeline">
                <h2>Timeline</h2>
                {selected.timeline.length === 0 ? <div className="conversation-state"><span>Chưa có hoạt động.</span></div> : <ol>{selected.timeline.map((item) => <li key={item.key}><span className={`timeline-dot ${item.kind}`} /><div><strong>{item.title}</strong>{item.detail && item.kind !== "lead" && <small>{item.detail}</small>}{item.conversation_public_id && <Link href={`/app/${workspace.slug}/conversations/${item.conversation_public_id}`}><MessageSquareText size={13} /> Mở hội thoại</Link>}{item.kind === "lead" && item.lead_id && <select aria-label="Trạng thái lead" disabled={busy || !canAdmin} onChange={(event) => void mutate(() => api.updateLeadStatus(workspace.id, item.lead_id!, event.target.value as LeadStatus))} value={item.detail as LeadStatus}>{Object.entries(leadLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}</div><time>{localDate(item.occurred_at)}</time></li>)}</ol>}
              </section>
            </div>
            <aside className="conversation-metadata">
              <h2>Hồ sơ</h2>
              <form className="metadata-form" onSubmit={(event) => { event.preventDefault(); if (canOperate || canAdmin) void mutate(() => api.updateContact(workspace.id, selected.contact.public_id, { state_version: selected.contact.state_version, display_name: displayName.trim() || null, update_display_name: true })); }}><label>Tên hiển thị<input aria-label="Tên hiển thị" disabled={busy || (!canAdmin && !canOperate)} maxLength={120} onChange={(event) => setDisplayName(event.target.value)} value={displayName} /></label><button disabled={busy || (!canAdmin && !canOperate)}>Lưu tên</button></form>
              <label>Phụ trách<select disabled={busy || workspace.role === "member"} onChange={(event) => void mutate(() => api.updateContact(workspace.id, selected.contact.public_id, { state_version: selected.contact.state_version, ...(event.target.value ? { assigned_member_id: Number(event.target.value) } : { clear_assignment: true }) }))} value={selected.contact.assigned_member_id ?? ""}><option value="">Chưa phân công</option>{members.map((member) => <option key={member.id} value={member.id}>{member.email}</option>)}</select></label>
              <h2>Thẻ</h2>
              <div className="tag-list">{selected.contact.tags.map((item) => <span key={item.id}>{item.name}</span>)}</div>
              <form className="metadata-form" onSubmit={(event) => { event.preventDefault(); if (tag.trim()) void mutate(async () => { await api.addContactTag(workspace.id, selected.contact.public_id, tag); setTag(""); }); }}><input aria-label="Thẻ mới" disabled={busy || (!canAdmin && !canOperate)} maxLength={48} onChange={(event) => setTag(event.target.value)} value={tag} /><button disabled={busy || (!canAdmin && !canOperate)}>Thêm</button></form>
              <h2>Ghi chú</h2>
              <div className="note-list">{selected.notes.map((item) => <article key={item.id}><strong>{item.author_email}</strong><p>{item.body}</p><time>{localDate(item.created_at)}</time></article>)}</div>
              <form className="metadata-form" onSubmit={(event) => { event.preventDefault(); if (note.trim()) void mutate(async () => { await api.addContactNote(workspace.id, selected.contact.public_id, note); setNote(""); }); }}><textarea aria-label="Ghi chú nội bộ" disabled={busy || (!canAdmin && !canOperate)} maxLength={2000} onChange={(event) => setNote(event.target.value)} value={note} /><button disabled={busy || (!canAdmin && !canOperate)}>Lưu ghi chú</button></form>
              {canAdmin && selected.duplicate_candidates.length > 0 && <><h2>Hồ sơ có thể trùng</h2><form className="metadata-form merge-form" onSubmit={(event) => { event.preventDefault(); const source = selected.duplicate_candidates.find((item) => item.public_id === mergeSource); if (!source || mergeReason.trim().length < 3) return; void mutate(async () => { const sourceDetail = await api.getContact(workspace.id, source.public_id); await api.mergeContacts(workspace.id, selected.contact.public_id, { source_public_id: source.public_id, source_state_version: sourceDetail.contact.state_version, target_state_version: selected.contact.state_version, reason: mergeReason }); setMergeSource(""); setMergeReason(""); }); }}><select aria-label="Hồ sơ nguồn" onChange={(event) => setMergeSource(event.target.value)} value={mergeSource}><option value="">Chọn hồ sơ</option>{selected.duplicate_candidates.map((item) => <option key={item.public_id} value={item.public_id}>{item.display_name || "Chưa có tên"} · {item.matching_identity_types.join(", ")}</option>)}</select><input aria-label="Lý do hợp nhất" maxLength={240} onChange={(event) => setMergeReason(event.target.value)} placeholder="Lý do xác nhận trùng" value={mergeReason} /><button disabled={busy || !mergeSource || mergeReason.trim().length < 3}><Merge size={14} /> Hợp nhất</button></form></>}
              {canAdmin && selected.active_merges.length > 0 && <><h2>Lịch sử hợp nhất</h2><div className="merge-history">{selected.active_merges.map((merge) => <article key={merge.id}><span>{merge.reason}</span><time>{localDate(merge.created_at)}</time><button disabled={busy} onClick={() => void mutate(() => api.reverseContactMerge(workspace.id, selected.contact.public_id, merge.id))} type="button"><RotateCcw size={13} /> Hoàn tác</button></article>)}</div></>}
            </aside>
          </div>
        </>}
      </article>
    </section>
  </>;
}
