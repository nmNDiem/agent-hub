"use client";

import {
  Check,
  Clipboard,
  Globe2,
  LoaderCircle,
  MessageCircle,
  Pause,
  Play,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { type CSSProperties, type FormEvent, useEffect, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type WidgetConfig, type WidgetConfigUpdate } from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";

type Props = {
  workspaceId: string;
  publicAgentId: string;
  canWrite: boolean;
  onChanged: () => Promise<unknown>;
};

function configDraft(config: WidgetConfig): WidgetConfigUpdate {
  return {
    display_name: config.display_name,
    greeting: config.greeting,
    brand_color: config.brand_color,
    launcher_position: config.launcher_position,
    allowed_origins: config.allowed_origins,
    handoff_url: config.handoff_url,
    handoff_label: config.handoff_label,
  };
}

function normalizeOrigin(value: string): string {
  const parsed = new URL(value.trim());
  if (!["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || (parsed.pathname !== "/" && parsed.pathname !== "")
    || parsed.search
    || parsed.hash) {
    throw new Error("invalid origin");
  }
  if (parsed.protocol === "http:"
    && !["localhost", "127.0.0.1", "[::1]", "::1"].includes(parsed.hostname)) {
    throw new Error("insecure origin");
  }
  return parsed.origin;
}

function statusLabel(config: WidgetConfig) {
  if (config.status === "published" && config.enabled) return "Đang hoạt động";
  if (config.status === "paused") return "Đã tạm dừng";
  return "Bản nháp";
}

export function WebChannelPanel({
  workspaceId,
  publicAgentId,
  canWrite,
  onChanged,
}: Props) {
  const [config, setConfig] = useState<WidgetConfig>();
  const [draft, setDraft] = useState<WidgetConfigUpdate>();
  const [originInput, setOriginInput] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<"save" | "publish" | "pause">();
  const [channelFeedback, setChannelFeedback] = useState<UiFeedback>();

  useEffect(() => {
    let active = true;
    api.getWidgetConfig(workspaceId, publicAgentId).then((result) => {
      if (!active) return;
      setConfig(result);
      setDraft(configDraft(result));
    }).catch((caught) => {
      if (active) {
        setChannelFeedback(toUiError(caught, {
          operation: "widget.load-config",
          fallback: "Không thể tải cấu hình kênh Web. Vui lòng thử lại.",
        }));
      }
    });
    return () => { active = false; };
  }, [publicAgentId, workspaceId]);

  function updateDraft(update: Partial<WidgetConfigUpdate>) {
    setDirty(true);
    setChannelFeedback(undefined);
    setDraft((current) => current ? { ...current, ...update } : current);
  }

  function addOrigin() {
    if (!draft || !originInput.trim()) return;
    try {
      const normalized = normalizeOrigin(originInput);
      if (!draft.allowed_origins.includes(normalized)) {
        updateDraft({ allowed_origins: [...draft.allowed_origins, normalized].sort() });
      }
      setOriginInput("");
    } catch {
      setChannelFeedback(feedback(
        "error",
        "Origin phải là HTTPS không có đường dẫn; HTTP chỉ dùng cho localhost.",
      ));
    }
  }

  async function saveCurrent(): Promise<WidgetConfig> {
    if (!draft) throw new Error("Widget config is not loaded");
    const saved = await api.updateWidgetConfig(workspaceId, publicAgentId, draft);
    setConfig(saved);
    setDraft(configDraft(saved));
    setDirty(false);
    await onChanged();
    return saved;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft || !dirty) return;
    setBusy("save");
    setChannelFeedback(undefined);
    try {
      await saveCurrent();
      setChannelFeedback(feedback("success", "Đã lưu cấu hình kênh Web."));
    } catch (caught) {
      setChannelFeedback(toUiError(caught, {
        operation: "widget.save-config",
        fallback: "Không thể lưu cấu hình kênh Web.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function publish() {
    setBusy("publish");
    setChannelFeedback(undefined);
    try {
      if (dirty) await saveCurrent();
      const published = await api.publishWidget(workspaceId, publicAgentId);
      setConfig(published);
      setDraft(configDraft(published));
      setDirty(false);
      await onChanged();
      setChannelFeedback(feedback("success", "Widget đã được phát hành lên website."));
    } catch (caught) {
      setChannelFeedback(toUiError(caught, {
        operation: "widget.publish",
        fallback: "Chưa thể phát hành widget. Hãy kiểm tra điều kiện sẵn sàng.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function pauseWidget() {
    setBusy("pause");
    setChannelFeedback(undefined);
    try {
      const paused = await api.pauseWidget(workspaceId, publicAgentId);
      setConfig(paused);
      setDraft(configDraft(paused));
      await onChanged();
      setChannelFeedback(feedback("success", "Widget đã được tạm dừng."));
    } catch (caught) {
      setChannelFeedback(toUiError(caught, {
        operation: "widget.pause",
        fallback: "Không thể tạm dừng widget lúc này.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function copySnippet() {
    if (!config?.embed_snippet) return;
    try {
      await navigator.clipboard.writeText(config.embed_snippet);
      setChannelFeedback(feedback("success", "Đã sao chép mã nhúng."));
    } catch {
      setChannelFeedback(feedback("error", "Không thể sao chép tự động. Hãy chọn và sao chép mã."));
    }
  }

  if (!config || !draft) {
    return <section className="web-channel-loading" aria-live="polite">
      {channelFeedback
        ? <FeedbackBanner feedback={channelFeedback} />
        : <><LoaderCircle className="spinner" size={20} /> Đang tải kênh Web…</>}
    </section>;
  }

  const readiness = [
    [config.readiness.has_allowed_origin, "Đã thêm website được phép"],
    [config.readiness.has_catalog_scope || config.readiness.has_knowledge, "Có nguồn dữ liệu: tri thức hoặc catalog"],
  ] as const;

  return <section className="web-channel-panel">
    <header className="web-channel-header">
      <div>
        <p className="eyebrow"><Globe2 aria-hidden="true" size={15} /> Kênh Website</p>
        <h2>Widget trò chuyện</h2>
        <p>Cấu hình website được phép, màu thương hiệu và mã nhúng công khai.</p>
      </div>
      <div className="web-channel-status-actions">
        <span className={`channel-status ${config.status}`}>{statusLabel(config)}</span>
        {canWrite && config.enabled && <button className="secondary-button compact-button" disabled={Boolean(busy)} onClick={() => void pauseWidget()} type="button"><Pause size={15} /> Tạm dừng</button>}
        {canWrite && !config.enabled && <button className="primary-button compact-button" disabled={Boolean(busy) || (!dirty && !config.readiness.can_publish)} onClick={() => void publish()} type="button">{busy === "publish" ? <LoaderCircle className="spinner" size={15} /> : <Play size={15} />} Phát hành</button>}
      </div>
    </header>
    {channelFeedback && <FeedbackBanner feedback={channelFeedback} />}
    <div className="web-channel-grid">
      <form className="web-channel-settings" onSubmit={(event) => void save(event)}>
        <fieldset disabled={!canWrite || Boolean(busy)}>
          <legend>Hiển thị</legend>
          <label>Tên hiển thị<input maxLength={160} onChange={(event) => updateDraft({ display_name: event.target.value })} required value={draft.display_name} /></label>
          <label>Lời chào<textarea maxLength={2000} onChange={(event) => updateDraft({ greeting: event.target.value || null })} rows={3} value={draft.greeting ?? ""} /></label>
          <div className="widget-brand-row">
            <label>Màu thương hiệu<span className="color-field"><input aria-label="Chọn màu thương hiệu" onChange={(event) => updateDraft({ brand_color: event.target.value.toUpperCase() })} type="color" value={draft.brand_color} /><input aria-label="Mã màu thương hiệu" maxLength={7} onChange={(event) => updateDraft({ brand_color: event.target.value.toUpperCase() })} pattern="#[0-9A-Fa-f]{6}" value={draft.brand_color} /></span></label>
            <fieldset className="launcher-position"><legend>Vị trí nút mở</legend><div><label><input checked={draft.launcher_position === "left"} name="launcher-position" onChange={() => updateDraft({ launcher_position: "left" })} type="radio" /> Trái</label><label><input checked={draft.launcher_position === "right"} name="launcher-position" onChange={() => updateDraft({ launcher_position: "right" })} type="radio" /> Phải</label></div></fieldset>
          </div>
        </fieldset>
        <fieldset disabled={!canWrite || Boolean(busy)}>
          <legend>Website được phép</legend>
          <p className="fieldset-help">Dùng origin chính xác, ví dụ <code>https://shop.example.com</code>. Không nhập đường dẫn.</p>
          <div className="origin-entry"><label className="sr-only" htmlFor="widget-origin">Thêm website</label><input id="widget-origin" onChange={(event) => setOriginInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addOrigin(); } }} placeholder="https://shop.example.com" value={originInput} /><button className="secondary-button icon-only-button" onClick={addOrigin} type="button"><Plus aria-hidden="true" size={16} /><span className="sr-only">Thêm website</span></button></div>
          <ul className="origin-list">{draft.allowed_origins.map((origin) => <li key={origin}><Globe2 aria-hidden="true" size={15} /><span>{origin}</span><button aria-label={`Xóa ${origin}`} onClick={() => updateDraft({ allowed_origins: draft.allowed_origins.filter((item) => item !== origin) })} type="button"><Trash2 size={15} /></button></li>)}{draft.allowed_origins.length === 0 && <li className="origin-empty">Chưa có website nào được phép.</li>}</ul>
        </fieldset>
        <fieldset disabled={!canWrite || Boolean(busy)}>
          <legend>Chuyển tiếp liên hệ</legend>
          <p className="fieldset-help">Tùy chọn. Dùng HTTPS, <code>mailto:</code> hoặc <code>tel:</code>; widget vẫn có form callback riêng.</p>
          <label>Đường dẫn liên hệ<input maxLength={500} onChange={(event) => updateDraft({ handoff_url: event.target.value || null })} placeholder="https://shop.example.com/contact" value={draft.handoff_url ?? ""} /></label>
          <label>Nhãn nút<input maxLength={80} onChange={(event) => updateDraft({ handoff_label: event.target.value || null })} placeholder="Liên hệ trực tiếp" value={draft.handoff_label ?? ""} /></label>
        </fieldset>
        <div className="widget-readiness"><strong>Sẵn sàng phát hành</strong><ul>{readiness.map(([ready, label]) => <li className={ready ? "ready" : "missing"} key={label}><Check aria-hidden="true" size={14} /> {label}</li>)}</ul></div>
        {canWrite && <div className="web-channel-save"><span>{dirty ? "Có thay đổi chưa lưu" : config.draft_differs ? "Bản nháp khác bản đang chạy" : "Đã đồng bộ"}</span><button className="secondary-button compact-button" disabled={!dirty || Boolean(busy)} type="submit">{busy === "save" ? <LoaderCircle className="spinner" size={15} /> : <Save size={15} />} Lưu thay đổi</button><button className="primary-button compact-button" disabled={Boolean(busy) || (!dirty && !config.readiness.can_publish)} onClick={() => void publish()} type="button">{busy === "publish" ? <LoaderCircle className="spinner" size={15} /> : <Play size={15} />} {config.active_revision ? "Phát hành bản mới" : "Phát hành"}</button></div>}
      </form>
      <aside className="web-channel-preview-column">
        <div className="widget-preview-card">
          <div className="widget-preview-heading"><div><strong>Xem trước</strong><span>Desktop · responsive</span></div><span className="preview-live-dot">Bản nháp</span></div>
          <div className="widget-site-preview">
            <div className="fake-site-bar"><i /><i /><i /><span /></div>
            <div className="fake-site-content"><span /><span /><span /></div>
            <div className={`widget-preview-window ${draft.launcher_position}`} style={{ "--widget-brand": draft.brand_color } as CSSProperties}>
              <header><span className="preview-avatar"><MessageCircle size={16} /></span><div><strong>{draft.display_name || "Chatbot"}</strong><small>Trợ lý AI</small></div></header>
              <div className="preview-transcript"><p>{draft.greeting || "Xin chào! Mình có thể giúp bạn tìm hiểu thông tin."}</p><div className="preview-suggestions"><span>Tìm hiểu thông tin</span><span>Chính sách hỗ trợ</span><span>Liên hệ trực tiếp</span></div></div>
              <div className="preview-composer"><span>Nhập tin nhắn…</span><i /></div>
            </div>
            <div className={`widget-preview-launcher ${draft.launcher_position}`} style={{ "--widget-brand": draft.brand_color } as CSSProperties}><MessageCircle size={21} /></div>
          </div>
        </div>
        <div className="embed-card">
          <div><strong>Mã nhúng</strong><span>Dán trước thẻ <code>&lt;/body&gt;</code> trên website.</span></div>
          {config.embed_snippet ? <><pre><code>{config.embed_snippet}</code></pre><button className="secondary-button compact-button" onClick={() => void copySnippet()} type="button"><Clipboard size={15} /> Sao chép mã</button></> : <p>Phát hành lần đầu để tạo mã nhúng.</p>}
        </div>
      </aside>
    </div>
  </section>;
}
