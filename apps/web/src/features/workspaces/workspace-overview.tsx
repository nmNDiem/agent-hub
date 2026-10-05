"use client";

import {
  Bot,
  CalendarDays,
  LoaderCircle,
  MessageSquareText,
  ShieldAlert,
  Sparkles,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type Dashboard } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

const leadStatus = { new: "Mới", contacted: "Đã liên hệ", closed: "Đã hoàn tất" };

function localDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function ActivityChart({ dashboard }: { dashboard: Dashboard }) {
  const { points, maximum } = useMemo(() => {
    const max = Math.max(...dashboard.activity.map((item) => item.conversations), 1);
    const chartPoints = dashboard.activity.map((item, index) => {
      const x = dashboard.activity.length === 1
        ? 50
        : (index / (dashboard.activity.length - 1)) * 100;
      const y = 94 - (item.conversations / max) * 82;
      return `${x},${y}`;
    }).join(" ");
    return { points: chartPoints, maximum: max };
  }, [dashboard.activity]);

  return <div className="overview-chart">
    <svg aria-hidden="true" preserveAspectRatio="none" viewBox="0 0 100 100">
      <line x1="0" x2="100" y1="94" y2="94" />
      <line x1="0" x2="100" y1="53" y2="53" />
      <line x1="0" x2="100" y1="12" y2="12" />
      <polyline points={points} />
    </svg>
    <div className="overview-chart-labels" aria-hidden="true">
      <span>{dashboard.activity[0]?.date}</span>
      <span>Tối đa {maximum}/ngày</span>
      <span>{dashboard.activity.at(-1)?.date}</span>
    </div>
    <table className="sr-only">
      <caption>Số hội thoại theo ngày, timezone {dashboard.timezone}</caption>
      <thead><tr><th>Ngày</th><th>Hội thoại</th></tr></thead>
      <tbody>{dashboard.activity.map((item) => <tr key={item.date}><td>{item.date}</td><td>{item.conversations}</td></tr>)}</tbody>
    </table>
  </div>;
}

export function WorkspaceOverview() {
  const params = useParams<{ workspaceSlug: string }>();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [days, setDays] = useState<7 | 30>(7);
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [feedback, setFeedback] = useState<UiFeedback>();
  const [loading, setLoading] = useState(true);
  const canView = workspace?.role === "owner" || workspace?.role === "admin";

  useEffect(() => {
    if (!workspace || !canView) return;
    let active = true;
    api.getDashboard(workspace.id, days).then((result) => {
      if (!active) return;
      setDashboard(result);
      setFeedback(undefined);
    }).catch((caught) => {
      if (active) setFeedback(toUiError(caught, {
        operation: "dashboard.load",
        fallback: "Không thể tải số liệu tổng quan.",
      }));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [canView, days, workspace]);

  if (workspaceError) return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  if (!me || !workspace) return <main className="centered-state"><LoaderCircle className="spinner" aria-hidden="true" /> Đang tải cửa hàng…</main>;

  const quotaPercent = dashboard
    ? Math.min((dashboard.usage.generated_turns / dashboard.usage.generated_turn_limit) * 100, 100)
    : 0;

  return <AppShell user={me.user} workspace={workspace} workspaces={me.workspaces}>
    <div className="page-heading overview-heading">
      <div><p className="eyebrow"><Sparkles size={15} /> Dữ liệu cửa hàng</p><h1>Tổng quan</h1><p>Số liệu thật trong timezone {workspace.timezone}; không bao gồm hội thoại đã xóa.</p></div>
      {canView && <div className="period-switch" aria-label="Khoảng thời gian">
        {([7, 30] as const).map((value) => <button aria-pressed={days === value} key={value} onClick={() => { setDays(value); setLoading(true); }} type="button">{value} ngày</button>)}
      </div>}
    </div>
    {!canView ? <section className="empty-state"><ShieldAlert size={28} /><h2>Không có quyền truy cập</h2><p>Chỉ owner hoặc admin được xem hội thoại và mức sử dụng.</p></section> : feedback ? <FeedbackBanner feedback={feedback} /> : loading || !dashboard ? <section className="overview-loading" aria-live="polite"><LoaderCircle className="spinner" /> Đang tổng hợp dữ liệu…</section> : <>
      <section className="overview-kpis" aria-label="Chỉ số tổng quan">
        <article><span><MessageSquareText /></span><small>Tổng hội thoại</small><strong>{dashboard.total_conversations.toLocaleString("vi-VN")}</strong><p>{days} ngày gần nhất</p></article>
        <article><span><Sparkles /></span><small>Phản hồi chatbot</small><strong>{dashboard.assistant_messages.toLocaleString("vi-VN")}</strong><p>Phản hồi đã hoàn tất</p></article>
        <article><span><Bot /></span><small>Chatbot đang hoạt động</small><strong>{dashboard.active_agents.toLocaleString("vi-VN")}</strong><p>{dashboard.enabled_web_channels} kênh Web đang bật</p></article>
        <article><span><CalendarDays /></span><small>Hạn mức tháng</small><strong>{dashboard.usage.generated_turns.toLocaleString("vi-VN")} / {dashboard.usage.generated_turn_limit.toLocaleString("vi-VN")}</strong><div className="quota-track"><i style={{ width: `${quotaPercent}%` }} /></div><p>Còn {dashboard.usage.generated_turns_remaining.toLocaleString("vi-VN")} lượt</p></article>
      </section>
      <section className="overview-activity card-surface">
        <header><div><h2>Hoạt động hội thoại</h2><p>Số hội thoại bắt đầu theo ngày · {dashboard.timezone}</p></div><span>{days} ngày</span></header>
        <ActivityChart dashboard={dashboard} />
      </section>
      <section className="overview-details">
        <article className="card-surface overview-list"><header><div><h2>Hội thoại gần đây</h2><p>Chỉ đọc, từ kênh Web</p></div><Link href={`/app/${workspace.slug}/conversations`}>Xem tất cả</Link></header>{dashboard.recent_conversations.length === 0 ? <div className="overview-empty"><MessageSquareText /><strong>Chưa có hội thoại</strong><span>Hoạt động thật sẽ xuất hiện sau lượt chat đầu tiên.</span></div> : <ul>{dashboard.recent_conversations.map((item) => <li key={item.public_id}><Link href={`/app/${workspace.slug}/conversations/${item.public_id}`}><span><strong>Khách ẩn danh</strong><small>{item.last_visitor_preview || "Không có nội dung xem trước"}</small></span><time dateTime={item.last_message_at}>{localDate(item.last_message_at)}</time></Link></li>)}</ul>}</article>
        <article className="card-surface overview-list"><header><div><h2>Khách tiềm năng gần đây</h2><p>Yêu cầu liên hệ đã có consent</p></div><Link href={`/app/${workspace.slug}/leads`}>Xem tất cả</Link></header>{dashboard.recent_leads.length === 0 ? <div className="overview-empty"><Users /><strong>Chưa có yêu cầu liên hệ</strong><span>Thông tin liên hệ không bắt buộc để chat.</span></div> : <ul>{dashboard.recent_leads.map((item, index) => <li key={`${item.created_at}-${index}`}><Link href={`/app/${workspace.slug}/leads`}><span><strong>{item.name || "Khách chưa cung cấp tên"}</strong><small>{item.agent_name} · {leadStatus[item.followup_status]}</small></span><time dateTime={item.created_at}>{localDate(item.created_at)}</time></Link></li>)}</ul>}</article>
      </section>
      <section className="usage-strip card-surface"><div><strong>Mức sử dụng tháng này</strong><span>{dashboard.usage.generation_model_calls} generation calls · {dashboard.usage.vision_model_calls} vision calls · {dashboard.usage.total_tokens.toLocaleString("vi-VN")} tokens đã ghi nhận</span></div><small>Không ước tính chi phí</small></section>
    </>}
  </AppShell>;
}
