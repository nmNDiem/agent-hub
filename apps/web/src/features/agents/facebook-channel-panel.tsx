"use client";

import {
  CheckCircle2,
  CircleAlert,
  LoaderCircle,
  MessagesSquare,
  RefreshCw,
  ShieldCheck,
  Unplug,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type FacebookConnection } from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";

type Props = {
  workspaceId: string;
  publicAgentId: string;
  canWrite: boolean;
};

const healthLabels: Record<FacebookConnection["health_state"], string> = {
  unknown: "Chưa kiểm tra",
  healthy: "Hoạt động tốt",
  permission_expired: "Quyền đã hết hạn",
  reauth_required: "Cần xác thực lại",
  webhook_subscription_failure: "Webhook chưa đăng ký",
  delivery_unknown: "Chưa rõ trạng thái gửi",
};

const queueLabels: Record<NonNullable<FacebookConnection["latest_queue_state"]>, string> = {
  queued: "Đang chờ phản hồi",
  running: "Đang tạo phản hồi",
  completed: "Đã tạo phản hồi",
  failed_retryable: "Sẽ thử lại",
  failed_terminal: "Tạo phản hồi thất bại",
  suppressed: "Tự động trả lời đã dừng",
};

const deliveryLabels: Record<NonNullable<FacebookConnection["latest_delivery_state"]>, string> = {
  queued: "Đang chờ gửi",
  sending: "Đang gửi",
  accepted: "Facebook đã nhận",
  delivered: "Đã giao",
  failed_retryable: "Sẽ thử gửi lại",
  failed_terminal: "Gửi thất bại",
};

function localDate(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
    : "Chưa xác minh";
}

export function FacebookChannelPanel({ workspaceId, publicAgentId, canWrite }: Props) {
  const [items, setItems] = useState<FacebookConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>();
  const [feedbackState, setFeedbackState] = useState<UiFeedback>();
  const [token, setToken] = useState("");
  const [reauthorizingId, setReauthorizingId] = useState<number>();
  const [reauthorizeToken, setReauthorizeToken] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setFeedbackState(undefined);
    try {
      const result = await api.listFacebookConnections(workspaceId);
      setItems(result.items.filter((item) => item.agent_public_id === publicAgentId));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "facebook.list-connections",
        fallback: "Không thể tải kết nối Facebook.",
      }));
    } finally {
      setLoading(false);
    }
  }, [publicAgentId, workspaceId]);

  useEffect(() => {
    let active = true;
    api.listFacebookConnections(workspaceId).then((result) => {
      if (active) {
        setItems(result.items.filter((item) => item.agent_public_id === publicAgentId));
      }
    }).catch((caught) => {
      if (active) {
        setFeedbackState(toUiError(caught, {
          operation: "facebook.list-connections",
          fallback: "Không thể tải kết nối Facebook.",
        }));
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [publicAgentId, workspaceId]);

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("connect");
    setFeedbackState(undefined);
    try {
      const connected = await api.connectFacebook(workspaceId, {
        agent_public_id: publicAgentId,
        page_access_token: token,
      });
      setToken("");
      setItems((current) => [connected, ...current.filter((item) => item.id !== connected.id)]);
      setFeedbackState(feedback("success", "Đã kết nối Facebook Page và xác minh webhook."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "facebook.connect",
        fallback: "Không thể kết nối Facebook Page. Token vẫn chưa được lưu.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function verify(connection: FacebookConnection) {
    setBusy(`verify-${connection.id}`);
    setFeedbackState(undefined);
    try {
      const updated = await api.verifyFacebookConnection(workspaceId, connection.id);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setFeedbackState(feedback("success", "Đã kiểm tra lại quyền và webhook Facebook."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "facebook.verify",
        fallback: "Kết nối cần được kiểm tra hoặc xác thực lại.",
      }));
      await load();
    } finally {
      setBusy(undefined);
    }
  }

  async function reauthorize(event: FormEvent<HTMLFormElement>, connection: FacebookConnection) {
    event.preventDefault();
    setBusy(`reauthorize-${connection.id}`);
    setFeedbackState(undefined);
    try {
      const updated = await api.reauthorizeFacebookConnection(
        workspaceId,
        connection.id,
        reauthorizeToken,
      );
      setReauthorizeToken("");
      setReauthorizingId(undefined);
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
      setFeedbackState(feedback("success", "Đã thay credential và xác thực lại đúng Facebook Page."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "facebook.reauthorize",
        fallback: "Không thể xác thực lại Facebook Page.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function revoke(connection: FacebookConnection) {
    if (!window.confirm(`Ngắt kết nối Facebook Page “${connection.display_name}”?`)) return;
    setBusy(`revoke-${connection.id}`);
    setFeedbackState(undefined);
    try {
      await api.revokeFacebookConnection(workspaceId, connection.id);
      await load();
      setFeedbackState(feedback("success", "Đã thu hồi kết nối Facebook tại AgentHub."));
    } catch (caught) {
      setFeedbackState(toUiError(caught, {
        operation: "facebook.revoke",
        fallback: "Kết nối đã được vô hiệu hóa cục bộ; credential có thể cần dọn lại.",
      }));
      await load();
    } finally {
      setBusy(undefined);
    }
  }

  if (loading) {
    return <section className="facebook-channel-state" aria-live="polite">
      <LoaderCircle className="spinner" size={20} /> Đang tải kết nối Facebook…
    </section>;
  }

  return <section className="facebook-channel-panel" aria-labelledby="facebook-channel-heading">
    <header className="facebook-channel-header">
      <div>
        <p className="eyebrow"><MessagesSquare aria-hidden="true" size={15} /> Facebook Messenger</p>
        <h2 id="facebook-channel-heading">Facebook Pages</h2>
        <p>Kết nối Page với chatbot này. Token chỉ được gửi một lần và không thể đọc lại.</p>
      </div>
      <span className="facebook-policy-note"><ShieldCheck size={16} /> Chỉ phản hồi trong 24 giờ</span>
    </header>
    {feedbackState && <FeedbackBanner feedback={feedbackState} onRetry={() => void load()} />}
    {items.length === 0 && <div className="facebook-empty">
      <MessagesSquare aria-hidden="true" size={30} />
      <strong>Chưa có Facebook Page</strong>
      <span>Kết nối Page đã cấp pages_messaging và quyền MESSAGE.</span>
    </div>}
    <div className="facebook-page-list">
      {items.map((connection) => <article className="facebook-page-card" key={connection.id}>
        <div className="facebook-page-summary">
          <span className="facebook-page-icon" aria-hidden="true"><MessagesSquare size={20} /></span>
          <div><h3>{connection.display_name}</h3><p>{connection.agent_name} · Page {connection.external_account_id}</p></div>
          <span className={`facebook-health ${connection.health_state}`}>
            {connection.health_state === "healthy" ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
            {connection.lifecycle_state === "revoked" ? "Đã thu hồi" : healthLabels[connection.health_state]}
          </span>
        </div>
        <dl className="facebook-page-facts">
          <div><dt>Xác minh gần nhất</dt><dd>{localDate(connection.last_verified_at)}</dd></div>
          <div><dt>Queue gần nhất</dt><dd>{connection.latest_queue_state ? queueLabels[connection.latest_queue_state] : "Chưa có"}</dd></div>
          <div><dt>Delivery gần nhất</dt><dd>{connection.latest_delivery_state ? deliveryLabels[connection.latest_delivery_state] : "Chưa có"}</dd></div>
        </dl>
        {connection.latest_safe_error_code && <p className="facebook-safe-error">Mã vận hành: {connection.latest_safe_error_code}</p>}
        {connection.lifecycle_state === "active" && canWrite && <div className="facebook-page-actions">
          <button className="secondary-button compact-button" disabled={Boolean(busy)} onClick={() => void verify(connection)} type="button">
            {busy === `verify-${connection.id}` ? <LoaderCircle className="spinner" size={15} /> : <RefreshCw size={15} />} Kiểm tra lại
          </button>
          <button className="secondary-button compact-button" disabled={Boolean(busy)} onClick={() => { setReauthorizingId(connection.id); setReauthorizeToken(""); }} type="button">Xác thực lại</button>
          <button className="danger-button compact-button" disabled={Boolean(busy)} onClick={() => void revoke(connection)} type="button">
            {busy === `revoke-${connection.id}` ? <LoaderCircle className="spinner" size={15} /> : <Unplug size={15} />} Thu hồi
          </button>
        </div>}
        {reauthorizingId === connection.id && <form className="facebook-reauthorize-form" onSubmit={(event) => void reauthorize(event, connection)}>
          <label htmlFor={`facebook-reauthorize-${connection.id}`}>Page access token mới</label>
          <input autoComplete="new-password" id={`facebook-reauthorize-${connection.id}`} minLength={1} onChange={(event) => setReauthorizeToken(event.target.value)} required type="password" value={reauthorizeToken} />
          <div><button className="primary-button compact-button" disabled={Boolean(busy)} type="submit">Thay credential</button><button className="secondary-button compact-button" onClick={() => { setReauthorizingId(undefined); setReauthorizeToken(""); }} type="button">Hủy</button></div>
        </form>}
      </article>)}
    </div>
    {canWrite && <form className="facebook-connect-form" onSubmit={connect}>
      <div><h3>Kết nối Page</h3><p>Token phải thuộc đúng Page và app đang cấu hình.</p></div>
      <label htmlFor="facebook-page-token">Page access token</label>
      <input autoComplete="new-password" id="facebook-page-token" minLength={1} onChange={(event) => setToken(event.target.value)} placeholder="Dán token một lần" required type="password" value={token} />
      <button className="primary-button compact-button" disabled={Boolean(busy)} type="submit">
        {busy === "connect" ? <LoaderCircle className="spinner" size={15} /> : <MessagesSquare size={15} />} Kết nối Facebook
      </button>
    </form>}
  </section>;
}
