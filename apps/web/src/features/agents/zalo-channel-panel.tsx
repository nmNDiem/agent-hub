"use client";

import {
  CheckCircle2,
  CircleAlert,
  LoaderCircle,
  MessageCircle,
  RefreshCw,
  ShieldCheck,
  Unplug,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type ZaloConnection } from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";

type Props = {
  workspaceId: string;
  publicAgentId: string;
  canWrite: boolean;
};

const healthLabels: Record<ZaloConnection["health_state"], string> = {
  unknown: "Chưa kiểm tra",
  healthy: "Hoạt động tốt",
  permission_expired: "Quyền đã hết hạn",
  reauth_required: "Cần kết nối lại",
  webhook_subscription_failure: "Cần cấu hình webhook",
  delivery_unknown: "Chưa rõ trạng thái gửi",
};

function localDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
    : "Chưa xác minh";
}

export function ZaloChannelPanel({ workspaceId, publicAgentId, canWrite }: Props) {
  const searchParams = useSearchParams();
  const [items, setItems] = useState<ZaloConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>();
  const [feedbackState, setFeedbackState] = useState<UiFeedback | undefined>(() => {
    if (searchParams?.get("oauth") === "success") {
      return feedback("success", "Đã cấp quyền Zalo OAuth. Hãy nhập OA secret key để kích hoạt webhook.");
    }
    if (searchParams?.get("oauth") === "error") {
      return feedback("error", "Không thể hoàn tất Zalo OAuth. Vui lòng thử kết nối lại.");
    }
    return undefined;
  });
  const [secretFor, setSecretFor] = useState<number>();
  const [webhookSecret, setWebhookSecret] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listZaloConnections(workspaceId);
      setItems(result.items.filter((item) => item.agent_public_id === publicAgentId));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "zalo.list-connections",
        fallback: "Không thể tải kết nối Zalo.",
      }));
    } finally {
      setLoading(false);
    }
  }, [publicAgentId, workspaceId]);

  useEffect(() => {
    let active = true;
    api.listZaloConnections(workspaceId).then((result) => {
      if (active) {
        setItems(result.items.filter((item) => item.agent_public_id === publicAgentId));
      }
    }).catch((caught) => {
      if (active) {
        setFeedbackState(toUiError(caught, {
          operation: "zalo.list-connections",
          fallback: "Không thể tải kết nối Zalo.",
        }));
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [publicAgentId, workspaceId]);

  async function beginOAuth(connectionId?: number) {
    setBusy(connectionId ? `oauth-${connectionId}` : "oauth");
    setFeedbackState(undefined);
    try {
      const result = await api.startZaloOAuth(workspaceId, {
        agent_public_id: publicAgentId,
        ...(connectionId ? { reauthorize_connection_id: connectionId } : {}),
      });
      window.location.assign(result.authorization_url);
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "zalo.oauth-start",
        fallback: "Không thể bắt đầu cấp quyền Zalo OAuth.",
      }));
      setBusy(undefined);
    }
  }

  async function saveWebhookSecret(event: FormEvent<HTMLFormElement>, connection: ZaloConnection) {
    event.preventDefault();
    setBusy(`secret-${connection.id}`);
    setFeedbackState(undefined);
    try {
      const updated = await api.setZaloWebhookSecret(workspaceId, connection.id, webhookSecret);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setWebhookSecret("");
      setSecretFor(undefined);
      setFeedbackState(feedback("success", "Đã lưu OA secret key trong kho bí mật và kích hoạt webhook."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "zalo.webhook-secret",
        fallback: "Không thể lưu OA secret key.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function verify(connection: ZaloConnection) {
    setBusy(`verify-${connection.id}`);
    setFeedbackState(undefined);
    try {
      const updated = await api.verifyZaloConnection(workspaceId, connection.id);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setFeedbackState(feedback("success", "Đã kiểm tra token, quyền quản lý OA và cấu hình webhook."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "zalo.verify",
        fallback: "Kết nối Zalo cần được kiểm tra hoặc cấp quyền lại.",
      }));
      await load();
    } finally {
      setBusy(undefined);
    }
  }

  async function revoke(connection: ZaloConnection) {
    if (!window.confirm(`Ngắt kết nối Zalo OA “${connection.display_name}”?`)) return;
    setBusy(`revoke-${connection.id}`);
    setFeedbackState(undefined);
    try {
      await api.revokeZaloConnection(workspaceId, connection.id);
      await load();
      setFeedbackState(feedback("success", "Đã thu hồi credential Zalo tại AgentHub."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "zalo.revoke",
        fallback: "Không thể hoàn tất thu hồi kết nối Zalo.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  if (loading) {
    return <section className="facebook-channel-state" aria-live="polite">
      <LoaderCircle className="spinner" size={20} /> Đang tải kết nối Zalo…
    </section>;
  }

  return <section className="facebook-channel-panel" aria-labelledby="zalo-channel-heading">
    <header className="facebook-channel-header">
      <div>
        <p className="eyebrow"><MessageCircle aria-hidden="true" size={15} /> Zalo Official Account</p>
        <h2 id="zalo-channel-heading">Zalo OA</h2>
        <p>Access token và refresh token được nhận qua OAuth và chỉ lưu phía server.</p>
      </div>
      <span className="facebook-policy-note"><ShieldCheck size={16} /> Chỉ phản hồi trong 48 giờ</span>
    </header>
    {feedbackState && <FeedbackBanner feedback={feedbackState} onRetry={() => void load()} />}
    {items.length === 0 && <div className="facebook-empty">
      <MessageCircle aria-hidden="true" size={30} />
      <strong>Chưa có Zalo OA</strong>
      <span>Cấp quyền OA qua OAuth chính thức, sau đó hoàn tất OA secret key cho webhook.</span>
    </div>}
    <div className="facebook-page-list">
      {items.map((connection) => <article className="facebook-page-card" key={connection.id}>
        <div className="facebook-page-summary">
          <span className="facebook-page-icon zalo-page-icon" aria-hidden="true"><MessageCircle size={20} /></span>
          <div><h3>{connection.display_name}</h3><p>{connection.agent_name} · OA {connection.external_account_id}</p></div>
          <span className={`facebook-health ${connection.health_state}`}>
            {connection.health_state === "healthy" ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
            {connection.lifecycle_state === "revoked" ? "Đã thu hồi" : healthLabels[connection.health_state]}
          </span>
        </div>
        <dl className="facebook-page-facts">
          <div><dt>Xác minh gần nhất</dt><dd>{localDate(connection.last_verified_at)}</dd></div>
          <div><dt>OAuth token</dt><dd>Tự động làm mới</dd></div>
          <div><dt>Webhook</dt><dd>{connection.webhook_configured ? "Đã có secret" : "Chưa có secret"}</dd></div>
        </dl>
        {connection.lifecycle_state === "active" && canWrite && <div className="facebook-page-actions">
          <button className="secondary-button compact-button" disabled={Boolean(busy)} onClick={() => void verify(connection)} type="button">
            {busy === `verify-${connection.id}` ? <LoaderCircle className="spinner" size={15} /> : <RefreshCw size={15} />} Kiểm tra
          </button>
          <button className="secondary-button compact-button" disabled={Boolean(busy)} onClick={() => void beginOAuth(connection.id)} type="button">
            {busy === `oauth-${connection.id}` ? <LoaderCircle className="spinner" size={15} /> : <RefreshCw size={15} />} Kết nối lại OAuth
          </button>
          <button className="secondary-button compact-button" disabled={Boolean(busy)} onClick={() => { setSecretFor(connection.id); setWebhookSecret(""); }} type="button">{connection.webhook_configured ? "Đổi OA secret" : "Nhập OA secret"}</button>
          <button className="danger-button compact-button" disabled={Boolean(busy)} onClick={() => void revoke(connection)} type="button">
            {busy === `revoke-${connection.id}` ? <LoaderCircle className="spinner" size={15} /> : <Unplug size={15} />} Thu hồi
          </button>
        </div>}
        {secretFor === connection.id && <form className="facebook-reauthorize-form" onSubmit={(event) => void saveWebhookSecret(event, connection)}>
          <label htmlFor={`zalo-webhook-secret-${connection.id}`}>OA secret key dùng để xác minh X-ZEvent-Signature</label>
          <input autoComplete="new-password" id={`zalo-webhook-secret-${connection.id}`} minLength={16} onChange={(event) => setWebhookSecret(event.target.value)} required type="password" value={webhookSecret} />
          <div><button className="primary-button compact-button" disabled={Boolean(busy)} type="submit">Lưu bí mật</button><button className="secondary-button compact-button" onClick={() => { setSecretFor(undefined); setWebhookSecret(""); }} type="button">Hủy</button></div>
        </form>}
      </article>)}
    </div>
    {canWrite && <div className="facebook-connect-form">
      <div><h3>Kết nối Zalo OA</h3><p>Bạn sẽ được chuyển tới Zalo để chọn OA và cấp quyền. AgentHub không yêu cầu dán token.</p></div>
      <button className="primary-button compact-button" disabled={Boolean(busy)} onClick={() => void beginOAuth()} type="button">
        {busy === "oauth" ? <LoaderCircle className="spinner" size={15} /> : <MessageCircle size={15} />} Kết nối bằng Zalo OAuth
      </button>
    </div>}
  </section>;
}
