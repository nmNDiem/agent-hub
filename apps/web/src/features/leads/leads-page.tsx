"use client";

import { Download, LoaderCircle, PhoneCall, Users } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type Lead, type LeadStatus } from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

const statusLabels: Record<LeadStatus, string> = {
  new: "Mới",
  contacted: "Đã liên hệ",
  closed: "Đã hoàn tất",
};

function localDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function LeadsPage() {
  const params = useParams<{ workspaceSlug: string }>();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [items, setItems] = useState<Lead[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<LeadStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>();
  const [pageFeedback, setPageFeedback] = useState<UiFeedback>();
  const canManage = workspace?.role === "owner" || workspace?.role === "admin";

  useEffect(() => {
    if (!workspace) return;
    if (!canManage) return;
    let active = true;
    api.listLeads(workspace.id, {
      followupStatus: statusFilter || undefined,
      limit: 20,
    }).then((result) => {
      if (!active) return;
      setItems(result.items);
      setNextCursor(result.next_cursor);
    }).catch((caught) => {
      if (active) setPageFeedback(toUiError(caught, {
        operation: "leads.load",
        fallback: "Không thể tải danh sách khách tiềm năng.",
      }));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [canManage, statusFilter, workspace]);

  async function loadMore() {
    if (!workspace || !nextCursor) return;
    setBusy("more");
    try {
      const result = await api.listLeads(workspace.id, {
        followupStatus: statusFilter || undefined,
        cursor: nextCursor,
        limit: 20,
      });
      setItems((current) => [...current, ...result.items]);
      setNextCursor(result.next_cursor);
    } catch (caught) {
      setPageFeedback(toUiError(caught, {
        operation: "leads.load-more",
        fallback: "Không thể tải thêm khách tiềm năng.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function updateStatus(lead: Lead, followupStatus: LeadStatus) {
    if (!workspace) return;
    setBusy(`status-${lead.id}`);
    setPageFeedback(undefined);
    try {
      const updated = await api.updateLeadStatus(workspace.id, lead.id, followupStatus);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setPageFeedback(feedback("success", "Đã cập nhật trạng thái theo dõi."));
    } catch (caught) {
      setPageFeedback(toUiError(caught, {
        operation: "leads.update-status",
        fallback: "Không thể cập nhật trạng thái theo dõi.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function exportCsv() {
    if (!workspace) return;
    setBusy("export");
    setPageFeedback(undefined);
    try {
      const blob = await api.exportLeads(workspace.id, statusFilter || undefined);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "agenthub-leads.csv";
      link.click();
      URL.revokeObjectURL(url);
      setPageFeedback(feedback("success", "Đã tạo tệp CSV an toàn."));
    } catch (caught) {
      setPageFeedback(toUiError(caught, {
        operation: "leads.export",
        fallback: "Không thể xuất danh sách khách tiềm năng.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  if (workspaceError) return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  if (!me || !workspace) return <main className="centered-state"><LoaderCircle className="spinner" aria-hidden="true" /> Đang tải cửa hàng…</main>;

  return <AppShell user={me.user} workspace={workspace} workspaces={me.workspaces}>
    <div className="page-heading leads-heading">
      <div><p className="eyebrow"><Users aria-hidden="true" size={15} /> Liên hệ có đồng ý</p><h1>Khách tiềm năng</h1><p>Theo dõi yêu cầu callback đã có consent. Dữ liệu local pilot tự hết hạn sau 30 ngày.</p></div>
      {canManage && <button className="secondary-button" disabled={Boolean(busy)} onClick={() => void exportCsv()} type="button">{busy === "export" ? <LoaderCircle className="spinner" size={16} /> : <Download size={16} />} Xuất CSV</button>}
    </div>
    {!canManage ? <section className="empty-state"><h2>Không có quyền truy cập</h2><p>Chỉ owner hoặc admin được xem thông tin liên hệ của khách.</p></section> : <>
      {pageFeedback && <FeedbackBanner feedback={pageFeedback} />}
      <section className="leads-card">
        <header className="leads-toolbar"><div><strong>Yêu cầu liên hệ</strong><span>{items.length} mục đang hiển thị</span></div><label>Trạng thái<select aria-label="Lọc theo trạng thái" onChange={(event) => { setLoading(true); setPageFeedback(undefined); setStatusFilter(event.target.value as LeadStatus | ""); }} value={statusFilter}><option value="">Tất cả</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></header>
        {loading ? <div className="leads-state"><LoaderCircle className="spinner" aria-hidden="true" /> Đang tải khách tiềm năng…</div> : items.length === 0 ? <div className="leads-state"><PhoneCall aria-hidden="true" size={28} /><strong>Chưa có yêu cầu liên hệ</strong><span>Khách vẫn có thể chat mà không cần để lại email hoặc số điện thoại.</span></div> : <div className="leads-table-wrap"><table className="leads-table"><thead><tr><th>Khách</th><th>Liên hệ</th><th>Chatbot</th><th>Thời gian</th><th>Hạn lưu</th><th>Trạng thái</th></tr></thead><tbody>{items.map((lead) => <tr key={lead.id}><td><strong>{lead.name || "Khách chưa cung cấp tên"}</strong><small>Consent: {lead.consent_text_version}</small></td><td><span>{lead.email || "—"}</span><small>{lead.phone || "—"}</small></td><td><span>{lead.agent_name}</span><small title={lead.conversation_public_id}>{lead.conversation_public_id}</small></td><td><time dateTime={lead.created_at} title={lead.created_at}>{localDate(lead.created_at)}</time></td><td><time dateTime={lead.retention_until} title={lead.retention_until}>{localDate(lead.retention_until)}</time></td><td><label className="sr-only" htmlFor={`lead-status-${lead.id}`}>Trạng thái của {lead.name || "khách"}</label><select className={`lead-status ${lead.followup_status}`} disabled={busy === `status-${lead.id}`} id={`lead-status-${lead.id}`} onChange={(event) => void updateStatus(lead, event.target.value as LeadStatus)} value={lead.followup_status}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td></tr>)}</tbody></table></div>}
        {nextCursor && <footer className="leads-footer"><button className="secondary-button" disabled={busy === "more"} onClick={() => void loadMore()} type="button">{busy === "more" && <LoaderCircle className="spinner" size={15} />} Tải thêm</button></footer>}
      </section>
    </>}
  </AppShell>;
}
