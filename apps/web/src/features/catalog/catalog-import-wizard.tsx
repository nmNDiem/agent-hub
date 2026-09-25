"use client";

import { CheckCircle2, FileSpreadsheet, LoaderCircle, Upload, XCircle } from "lucide-react";
import { DragEvent, useRef, useState } from "react";

import { api, ApiError, type CatalogImportJob, type UniversalImportResult } from "@/lib/api";

type Props = { workspaceId: string; onCommitted: () => Promise<void> };
type WizardState = "upload" | "analyzing" | "review" | "committing" | "success";

const allowedExtensions = [".csv", ".xls", ".xlsx"];
const maxBytes = 10 * 1024 * 1024;

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể xử lý tệp. Vui lòng thử lại.";
}

function validateFile(file: File): string | undefined {
  const lower = file.name.toLowerCase();
  if (!allowedExtensions.some((extension) => lower.endsWith(extension))) {
    return "Chỉ hỗ trợ tệp CSV, XLS hoặc XLSX.";
  }
  if (file.size > maxBytes) return "Tệp vượt quá giới hạn 10 MB.";
  return undefined;
}

export function CatalogImportWizard({ workspaceId, onCommitted }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<WizardState>("upload");
  const [job, setJob] = useState<CatalogImportJob>();
  const [result, setResult] = useState<UniversalImportResult>();
  const [error, setError] = useState<string>();
  const [dragging, setDragging] = useState(false);

  async function analyze(file: File) {
    const validation = validateFile(file);
    if (validation) { setError(validation); return; }
    setError(undefined);
    setState("analyzing");
    try {
      const next = await api.createCatalogImport(workspaceId, file);
      setJob(next);
      setState(next.status === "failed" ? "upload" : "review");
      if (next.status === "failed") {
        setError(String(next.result?.message ?? "Không thể đọc tệp catalog."));
      }
    } catch (caught) {
      setError(message(caught));
      setState("upload");
    }
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void analyze(file);
  }

  async function resolve(issueId: number) {
    if (!job) return;
    setError(undefined);
    try {
      setJob(await api.resolveCatalogImportIssue(workspaceId, job.id, issueId, { action: "ignore" }));
    } catch (caught) { setError(message(caught)); }
  }

  async function commit() {
    if (!job) return;
    setState("committing");
    setError(undefined);
    try {
      const committed = await api.commitCatalogImportJob(workspaceId, job.id, crypto.randomUUID());
      setResult(committed);
      setState("success");
      await onCommitted();
    } catch (caught) {
      setError(message(caught));
      setState("review");
    }
  }

  function reset() {
    setState("upload"); setJob(undefined); setResult(undefined); setError(undefined);
    if (inputRef.current) inputRef.current.value = "";
  }

  const openIssues = job?.issues.filter((issue) => issue.status === "open") ?? [];
  const blocking = openIssues.some((issue) => ["error", "needs_confirmation"].includes(issue.severity));

  return (
    <section className="import-wizard" aria-labelledby="import-wizard-title">
      <div className="card-heading">
        <div><h3 id="import-wizard-title">Nhập catalog</h3><p>Hệ thống tự nhận diện cấu trúc, không cần chọn nền tảng nguồn.</p></div>
        <FileSpreadsheet aria-hidden="true" />
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}

      {state === "upload" && (
        <div
          className={`upload-dropzone ${dragging ? "is-dragging" : ""}`}
          onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()} onDrop={drop}
        >
          <Upload size={24} aria-hidden="true" /><strong>Kéo thả CSV, XLS hoặc XLSX</strong>
          <span>hoặc chọn tệp trên máy · tối đa 10 MB</span>
          <input ref={inputRef} aria-label="Chọn tệp catalog" accept=".csv,.xls,.xlsx" type="file"
            onChange={(event) => { const file = event.target.files?.[0]; if (file) void analyze(file); }} />
        </div>
      )}

      {state === "analyzing" && <div className="import-progress" role="status"><LoaderCircle className="spinner" /><strong>Đang phân tích cấu trúc catalog…</strong><span>Giữ nguyên trang trong giây lát.</span></div>}

      {state === "review" && job && (
        <div className="import-review">
          <p className="import-file"><strong>{job.original_filename}</strong><span>{job.file_type?.toUpperCase()} · {Number(job.metadata.rows ?? 0)} hàng</span></p>
          <div className="import-summary" aria-label="Tóm tắt thay đổi">
            {(["products", "variants", "images"] as const).map((kind) => <article key={kind}><strong>{kind === "products" ? "Sản phẩm" : kind === "variants" ? "Biến thể" : "Ảnh"}</strong><span>+ {job.summary[kind].create} tạo mới</span><span>~ {job.summary[kind].update} cập nhật</span><span>= {job.summary[kind].unchanged} giữ nguyên</span><span>! {job.summary[kind].conflict} xung đột</span></article>)}
          </div>
          {openIssues.length > 0 && <div className="import-issues"><h4>Cần bạn xác nhận ({openIssues.length})</h4>{openIssues.map((issue) => <article key={issue.id}><div><strong>{issue.message}</strong><small>{issue.source_location.sheet ? `Sheet ${issue.source_location.sheet}, hàng ${issue.source_location.row ?? "—"}` : "Toàn tệp"}</small></div>{issue.severity === "needs_confirmation" ? <button className="secondary-button" type="button" onClick={() => void resolve(issue.id)}>Bỏ qua cột/hàng này</button> : <span className="form-error">Hãy sửa tệp và tải lại</span>}</article>)}</div>}
          <div className="form-actions"><button className="secondary-button" onClick={reset} type="button">Chọn tệp khác</button><button className="primary-button" disabled={blocking || job.status !== "ready"} onClick={() => void commit()} type="button">Nhập catalog</button></div>
        </div>
      )}

      {state === "committing" && <div className="import-progress" role="status"><LoaderCircle className="spinner" /><strong>Đang ghi catalog trong một transaction…</strong></div>}

      {state === "success" && result && <div className="import-success" role="status"><CheckCircle2 aria-hidden="true" /><div><strong>Import hoàn tất</strong><p>{result.products_created} sản phẩm mới, {result.products_updated} cập nhật · {result.variants_created} biến thể mới.</p></div><button className="secondary-button" onClick={reset} type="button">Nhập tệp khác</button></div>}
      {job?.status === "failed" && <XCircle className="import-failed-icon" aria-hidden="true" />}
    </section>
  );
}
