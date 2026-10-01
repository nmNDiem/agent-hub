"use client";

import {
  AlertCircle,
  BookOpen,
  FileText,
  LoaderCircle,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  api,
  ApiError,
  type IngestionStatus,
  type KnowledgeBase,
  type KnowledgeDocument,
} from "@/lib/api";
import { useWorkspace } from "@/lib/use-workspace";

const activeStatuses = new Set<IngestionStatus>([
  "uploading",
  "queued",
  "processing",
  "retry_scheduled",
]);

const statusLabels: Record<IngestionStatus, string> = {
  uploading: "Đang tải lên",
  awaiting_profile: "Chờ cấu hình embedding",
  queued: "Đang xếp hàng",
  processing: "Đang xử lý",
  retry_scheduled: "Đã lên lịch thử lại",
  succeeded: "Sẵn sàng",
  failed: "Thất bại",
  cancelled: "Đã hủy",
};

function messageFrom(error: unknown) {
  return error instanceof ApiError ? error.message : "Không thể hoàn tất thao tác. Vui lòng thử lại.";
}

export function KnowledgePage() {
  const params = useParams<{ workspaceSlug: string }>();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [selectedBaseId, setSelectedBaseId] = useState<number>();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>();
  const [error, setError] = useState<string>();
  const uploadController = useRef<AbortController | undefined>(undefined);

  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";
  const selectedBase = bases.find((item) => item.id === selectedBaseId);

  async function loadBases(workspaceId: string) {
    const result = await api.listKnowledgeBases(workspaceId);
    setBases(result.items);
    if (result.items.length === 0) setDocuments([]);
    setSelectedBaseId((current) =>
      current && result.items.some((item) => item.id === current) ? current : result.items[0]?.id,
    );
  }

  async function loadDocuments(workspaceId: string, baseId: number, quiet = false) {
    if (!quiet) setLoading(true);
    try {
      const result = await api.listKnowledgeDocuments(workspaceId, baseId);
      setDocuments(result.items);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  useEffect(() => {
    if (!workspace) return;
    let active = true;
    api.listKnowledgeBases(workspace.id).then((result) => {
      if (!active) return;
      setBases(result.items);
      if (result.items.length === 0) setDocuments([]);
      setSelectedBaseId(result.items[0]?.id);
    }).catch((caught) => {
      if (active) setError(messageFrom(caught));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [workspace]);

  useEffect(() => {
    if (!workspace || !selectedBaseId) {
      return;
    }
    let active = true;
    api.listKnowledgeDocuments(workspace.id, selectedBaseId).then((result) => {
      if (active) setDocuments(result.items);
    }).catch((caught) => {
      if (active) setError(messageFrom(caught));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedBaseId, workspace]);

  useEffect(() => {
    if (!workspace || !selectedBaseId || !documents.some((item) => activeStatuses.has(item.ingestion_job.status))) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadDocuments(workspace.id, selectedBaseId, true);
    }, 4_000);
    return () => window.clearInterval(timer);
  }, [documents, selectedBaseId, workspace]);

  async function createBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const form = new FormData(event.currentTarget);
    setBusy("base");
    setError(undefined);
    try {
      const created = await api.createKnowledgeBase(workspace.id, {
        name: String(form.get("name")),
        kind: String(form.get("kind")) as KnowledgeBase["kind"],
      });
      event.currentTarget.reset();
      await loadBases(workspace.id);
      setSelectedBaseId(created.id);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function createManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selectedBaseId) return;
    const form = new FormData(event.currentTarget);
    setBusy("manual");
    setError(undefined);
    try {
      await api.createManualKnowledge(
        workspace.id,
        selectedBaseId,
        {
          title: String(form.get("title")),
          kind: String(form.get("kind")) as "profile" | "faq" | "policy" | "size_guidance",
          content: String(form.get("content")),
        },
        crypto.randomUUID(),
      );
      event.currentTarget.reset();
      await Promise.all([
        loadDocuments(workspace.id, selectedBaseId),
        loadBases(workspace.id),
      ]);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selectedBaseId) return;
    const formElement = event.currentTarget;
    const values = new FormData(formElement);
    const file = values.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Hãy chọn một tệp PDF hoặc TXT.");
      return;
    }
    if (!["application/pdf", "text/plain"].includes(file.type)) {
      setError("Chỉ chấp nhận tệp PDF hoặc TXT.");
      return;
    }
    const payload = new FormData();
    payload.set("file", file);
    payload.set("title", String(values.get("title")) || file.name.replace(/\.[^.]+$/, ""));
    payload.set("kind", "document");
    uploadController.current = new AbortController();
    setBusy("upload");
    setError(undefined);
    try {
      await api.uploadKnowledgeDocument(
        workspace.id,
        selectedBaseId,
        payload,
        crypto.randomUUID(),
        uploadController.current.signal,
      );
      formElement.reset();
      await Promise.all([
        loadDocuments(workspace.id, selectedBaseId),
        loadBases(workspace.id),
      ]);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") setError("Đã dừng tải tệp.");
      else setError(messageFrom(caught));
    } finally {
      uploadController.current = undefined;
      setBusy(undefined);
    }
  }

  async function retry(document: KnowledgeDocument) {
    if (!workspace) return;
    setBusy(`retry-${document.id}`);
    setError(undefined);
    try {
      await api.retryIngestionJob(workspace.id, document.ingestion_job.id);
      await loadDocuments(workspace.id, document.knowledge_base_id);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function remove(document: KnowledgeDocument) {
    if (!workspace || !confirm(`Xóa “${document.title}” khỏi truy xuất?`)) return;
    setBusy(`delete-${document.id}`);
    setError(undefined);
    try {
      await api.deleteKnowledgeDocument(workspace.id, document.knowledge_base_id, document.id);
      await Promise.all([
        loadDocuments(workspace.id, document.knowledge_base_id),
        loadBases(workspace.id),
      ]);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(undefined);
    }
  }

  if (workspaceError) return <main className="center-state"><p role="alert">{workspaceError}</p></main>;
  if (!me || !workspace) return <main className="center-state" aria-live="polite">Đang tải cửa hàng…</main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="page-heading catalog-heading">
        <div><p className="eyebrow">Nguồn grounding</p><h1>Tri thức</h1><p>Quản lý dữ liệu đã kiểm chứng mà chatbot được phép sử dụng.</p></div>
        {!canWrite && <span className="status-pill archived">Chỉ đọc</span>}
      </section>
      {error && <p className="form-error" role="alert"><AlertCircle aria-hidden="true" size={16} /> {error}</p>}
      <div className="knowledge-layout">
        <aside className="knowledge-bases-card">
          <div className="card-heading"><div><h2>Kho tri thức</h2><p>{bases.length} nguồn đang hoạt động</p></div><BookOpen aria-hidden="true" /></div>
          {canWrite && (
            <form className="knowledge-base-form" onSubmit={createBase}>
              <input aria-label="Tên kho tri thức" name="name" placeholder="Ví dụ: Chính sách cửa hàng" required />
              <select aria-label="Loại kho tri thức" defaultValue="general" name="kind">
                <option value="shop">Cửa hàng</option><option value="faq">FAQ</option>
                <option value="policy">Chính sách</option><option value="general">Chung</option>
              </select>
              <button className="secondary-button" disabled={busy === "base"} type="submit"><Plus size={16} /> Tạo kho</button>
            </form>
          )}
          <div className="knowledge-base-list" role="listbox" aria-label="Kho tri thức">
            {bases.map((base) => (
              <button
                aria-selected={selectedBaseId === base.id}
                className="knowledge-base-item"
                key={base.id}
                onClick={() => setSelectedBaseId(base.id)}
                role="option"
                type="button"
              >
                <span><strong>{base.name}</strong><small>{base.kind} · {base.document_count} tài liệu</small></span>
                <span aria-hidden="true">›</span>
              </button>
            ))}
            {!loading && bases.length === 0 && <p className="compact-empty">Chưa có kho tri thức.</p>}
          </div>
        </aside>
        <section className="knowledge-documents-card">
          <div className="card-heading"><div><h2>{selectedBase?.name ?? "Tài liệu"}</h2><p>Trạng thái được cập nhật từ pipeline ingestion thật.</p></div><FileText aria-hidden="true" /></div>
          {canWrite && selectedBase && (
            <div className="knowledge-input-grid">
              <form className="catalog-form" onSubmit={createManual}>
                <h3>Nhập nội dung</h3>
                <label>Tiêu đề<input name="title" required /></label>
                <label>Loại<select defaultValue="faq" name="kind"><option value="profile">Hồ sơ cửa hàng</option><option value="faq">FAQ</option><option value="policy">Chính sách</option><option value="size_guidance">Hướng dẫn kích cỡ</option></select></label>
                <label>Nội dung<textarea name="content" required rows={5} /></label>
                <button className="primary-button compact-button" disabled={busy === "manual"} type="submit">{busy === "manual" && <LoaderCircle className="spinner" size={16} />} Lưu và xử lý</button>
              </form>
              <form className="catalog-form" onSubmit={uploadFile}>
                <h3>Tải tài liệu</h3>
                <label>Tiêu đề<input name="title" placeholder="Mặc định dùng tên tệp" /></label>
                <label className="upload-dropzone"><Upload aria-hidden="true" /><strong>Chọn PDF hoặc TXT</strong><small>Máy chủ kiểm tra loại tệp và giới hạn dung lượng.</small><input accept=".pdf,.txt,application/pdf,text/plain" name="file" required type="file" /></label>
                <div className="form-actions">
                  <button className="primary-button compact-button" disabled={busy === "upload"} type="submit">{busy === "upload" && <LoaderCircle className="spinner" size={16} />} Tải lên</button>
                  {busy === "upload" && <button className="secondary-button" onClick={() => uploadController.current?.abort()} type="button">Dừng tải lên</button>}
                </div>
              </form>
            </div>
          )}
          <div className="knowledge-document-list" aria-busy={loading} aria-live="polite">
            {loading && <p className="compact-empty"><LoaderCircle className="spinner" size={18} /> Đang tải tài liệu…</p>}
            {!loading && selectedBase && documents.length === 0 && <p className="compact-empty">Kho này chưa có tài liệu.</p>}
            {!loading && !selectedBase && <p className="compact-empty">Chọn hoặc tạo một kho tri thức để bắt đầu.</p>}
            {documents.map((document) => {
              const status = document.ingestion_job.status;
              return (
                <article className="knowledge-document" key={document.id}>
                  <span className="document-icon" aria-hidden="true"><FileText size={18} /></span>
                  <div className="document-copy"><strong>{document.title}</strong><small>{document.source_kind === "file" ? document.mime_type : "Nội dung thủ công"} · cập nhật {new Intl.DateTimeFormat("vi-VN").format(new Date(document.updated_at))}</small>{document.ingestion_job.last_error_code && <span className="document-error">Mã lỗi: {document.ingestion_job.last_error_code}</span>}</div>
                  <span className={`ingestion-status ${status}`}>{activeStatuses.has(status) && <LoaderCircle className="spinner" size={13} />}{statusLabels[status]}</span>
                  {canWrite && <div className="document-actions">{status === "failed" && document.ingestion_job.retryable && <button aria-label={`Thử lại ${document.title}`} className="icon-button" disabled={busy === `retry-${document.id}`} onClick={() => void retry(document)} title="Thử lại" type="button"><RefreshCw size={15} /></button>}<button aria-label={`Xóa ${document.title}`} className="icon-button danger-text" disabled={busy === `delete-${document.id}`} onClick={() => void remove(document)} title="Xóa" type="button"><Trash2 size={15} /></button></div>}
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
