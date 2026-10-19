"use client";

import {
  ArrowRightLeft,
  BarChart3,
  Bot,
  Clock3,
  LoaderCircle,
  MessageSquareText,
  ShieldAlert,
  ShoppingBag,
  UserCheck,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api, type AnalyticsBreakdown, type OperationalAnalytics } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

type Channel = "web" | "facebook" | "zalo";

const channelLabels: Record<Channel, string> = {
  web: "Website",
  facebook: "Facebook",
  zalo: "Zalo",
};

function integer(value: number): string {
  return value.toLocaleString("vi-VN");
}

function duration(value: number | null): string {
  if (value === null) return "Chưa có dữ liệu";
  if (value < 60) return `${Math.round(value)} giây`;
  if (value < 3_600) return `${Math.round(value / 60)} phút`;
  return `${(value / 3_600).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} giờ`;
}

function ActivityChart({ report }: { report: OperationalAnalytics }) {
  const maximum = useMemo(
    () => Math.max(
      ...report.activity.flatMap((item) => [item.inbound_messages, item.completed_replies]),
      1,
    ),
    [report.activity],
  );
  const labelStep = report.activity.length > 14 ? 5 : report.activity.length > 7 ? 2 : 1;
  return <>
    <div aria-hidden="true" className="analytics-bars">
      {report.activity.map((item, index) => <div className="analytics-bar-day" key={item.date}>
        <div className="analytics-bar-pair">
          <i className="analytics-bar-inbound" style={{ height: `${Math.max((item.inbound_messages / maximum) * 100, item.inbound_messages ? 4 : 0)}%` }} />
          <i className="analytics-bar-reply" style={{ height: `${Math.max((item.completed_replies / maximum) * 100, item.completed_replies ? 4 : 0)}%` }} />
        </div>
        <small>{index % labelStep === 0 || index === report.activity.length - 1 ? item.date.slice(5) : ""}</small>
      </div>)}
    </div>
    <div aria-hidden="true" className="analytics-legend">
      <span><i className="analytics-dot inbound" /> Tin đến</span>
      <span><i className="analytics-dot reply" /> Phản hồi</span>
    </div>
    <table className="sr-only">
      <caption>Hoạt động theo ngày, timezone {report.timezone}</caption>
      <thead><tr><th>Ngày</th><th>Hội thoại</th><th>Tin đến</th><th>Phản hồi</th></tr></thead>
      <tbody>{report.activity.map((item) => <tr key={item.date}><td>{item.date}</td><td>{item.conversations}</td><td>{item.inbound_messages}</td><td>{item.completed_replies}</td></tr>)}</tbody>
    </table>
  </>;
}

function BreakdownTable({ caption, items }: { caption: string; items: AnalyticsBreakdown[] }) {
  return <div className="analytics-table-wrap"><table className="analytics-table">
    <caption>{caption}</caption>
    <thead><tr><th>Nhóm</th><th>Hội thoại</th><th>Tin đến</th><th>Phản hồi</th><th>Giao thành công</th><th>Lỗi giao</th></tr></thead>
    <tbody>{items.map((item) => <tr key={item.key}>
      <th scope="row">{item.key in channelLabels ? channelLabels[item.key as Channel] : item.label}</th>
      <td>{integer(item.conversations)}</td>
      <td>{integer(item.inbound_messages)}</td>
      <td>{integer(item.completed_replies)}</td>
      <td>{item.delivery ? integer(item.delivery.delivered + item.delivery.accepted) : "Không áp dụng"}</td>
      <td>{item.delivery ? integer(item.delivery.failed_retryable + item.delivery.failed_terminal) : "Không áp dụng"}</td>
    </tr>)}</tbody>
  </table></div>;
}

export function AnalyticsPage() {
  const params = useParams<{ workspaceSlug: string }>();
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [days, setDays] = useState<7 | 30>(7);
  const [channel, setChannel] = useState<Channel | "">("");
  const [agentPublicId, setAgentPublicId] = useState("");
  const [report, setReport] = useState<OperationalAnalytics>();
  const [feedback, setFeedback] = useState<UiFeedback>();
  const [loading, setLoading] = useState(true);
  const canView = workspace?.role === "owner" || workspace?.role === "admin";

  useEffect(() => {
    if (!workspace || !canView) return;
    let active = true;
    api.getAnalytics(workspace.id, {
      days,
      channel: channel || undefined,
      agentPublicId: agentPublicId || undefined,
    }).then((result) => {
      if (!active) return;
      setReport(result);
      setFeedback(undefined);
    }).catch((caught) => {
      if (active) setFeedback(toUiError(caught, {
        operation: "analytics.load",
        fallback: "Không thể tải dữ liệu phân tích.",
      }));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [agentPublicId, canView, channel, days, workspace]);

  if (workspaceError) return <main className="centered-state"><FeedbackBanner feedback={workspaceError} /></main>;
  if (!me || !workspace) return <main className="centered-state"><LoaderCircle className="spinner" aria-hidden="true" /> Đang tải cửa hàng…</main>;

  return <>
    <div className="page-heading analytics-heading">
      <h1>Phân tích</h1>
      {canView && <div aria-label="Khoảng thời gian" className="period-switch">
        {([7, 30] as const).map((value) => <button aria-pressed={days === value} key={value} onClick={() => { setLoading(true); setDays(value); }} type="button">{value} ngày</button>)}
      </div>}
    </div>
    {!canView ? <section className="empty-state"><ShieldAlert size={28} /><h2>Không có quyền truy cập</h2><p>Chỉ owner hoặc admin được xem phân tích vận hành.</p></section> : <>
      <section aria-label="Bộ lọc phân tích" className="analytics-filters card-surface">
        <label>Kênh<select onChange={(event) => { setLoading(true); setChannel(event.target.value as Channel | ""); }} value={channel}><option value="">Tất cả kênh</option><option value="web">Website</option><option value="facebook">Facebook</option><option value="zalo">Zalo</option></select></label>
        <label>Chatbot<select onChange={(event) => { setLoading(true); setAgentPublicId(event.target.value); }} value={agentPublicId}><option value="">Tất cả chatbot</option>{report?.agent_options.map((agent) => <option key={agent.public_id} value={agent.public_id}>{agent.name}</option>)}</select></label>
        <small>Chỉ số từ sự kiện đã lưu · {workspace.timezone} · Không ước tính chi phí hay doanh thu</small>
      </section>
      {feedback ? <FeedbackBanner feedback={feedback} /> : loading || !report ? <section aria-live="polite" className="overview-loading"><LoaderCircle className="spinner" /> Đang tổng hợp dữ liệu…</section> : <>
        <section aria-label="Chỉ số vận hành" className="overview-kpis analytics-kpis">
          <article><span><MessageSquareText /></span><small>Hội thoại</small><strong>{integer(report.summary.conversations)}</strong><p>{integer(report.summary.inbound_messages)} tin nhắn đến</p></article>
          <article><span><Clock3 /></span><small>Phản hồi đầu</small><strong>{duration(report.first_response.average_seconds)}</strong><p>{integer(report.first_response.sample_count)} mẫu đo được</p></article>
          <article><span><UserCheck /></span><small>Chuyển đổi lead</small><strong>{report.lead_conversion.rate === null ? "Chưa có dữ liệu" : `${(report.lead_conversion.rate * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`}</strong><p>{report.lead_conversion.converted_conversations} / {report.lead_conversion.eligible_conversations} hội thoại</p></article>
          <article><span><ShieldAlert /></span><small>Chưa giải quyết</small><strong>{integer(report.resolution.unresolved)}</strong><p>{integer(report.summary.failed_replies)} phản hồi lỗi</p></article>
        </section>
        <section className="overview-activity card-surface analytics-activity">
          <header><div><h2>Hoạt động tin nhắn</h2><p>Tin đến và phản hồi hoàn tất · {report.timezone}</p></div><span>{days} ngày</span></header>
          <ActivityChart report={report} />
        </section>
        <section className="analytics-outcomes">
          <article className="card-surface"><span><Bot /></span><div><small>AI-only resolved</small><strong>{integer(report.resolution.ai_only_resolved)}</strong><p>Resolved, không takeover hay human reply</p></div></article>
          <article className="card-surface"><span><ArrowRightLeft /></span><div><small>Human handled</small><strong>{integer(report.resolution.human_handled_resolved)}</strong><p>{integer(report.resolution.handoffs)} lượt bàn giao</p></div></article>
          <article className="card-surface"><span><Clock3 /></span><div><small>Phản hồi của người phụ trách</small><strong>{duration(report.human_response.average_seconds)}</strong><p>{integer(report.human_response.sample_count)} mẫu đo được</p></div></article>
        </section>
        {report.summary.conversations === 0 ? <section className="empty-state"><BarChart3 size={28} /><h2>Chưa có hoạt động trong kỳ</h2><p>Thử đổi kênh, chatbot hoặc khoảng thời gian.</p></section> : <>
          <section className="analytics-grid">
            <article className="card-surface"><h2>Theo kênh</h2><BreakdownTable caption="Hoạt động và kết quả giao theo kênh" items={report.by_channel} /></article>
            <article className="card-surface"><h2>Theo chatbot</h2><BreakdownTable caption="Hoạt động và kết quả giao theo chatbot" items={report.by_agent} /></article>
          </section>
          <section className="card-surface analytics-products"><header><div><h2>Sản phẩm được hiển thị</h2><p>Lượt product card thực tế; không phải click hay doanh số.</p></div><ShoppingBag /></header>{report.product_interest.length ? <div className="analytics-table-wrap"><table className="analytics-table"><caption>Top sản phẩm theo lượt hiển thị</caption><thead><tr><th>Sản phẩm</th><th>Lượt hiển thị</th><th>Hội thoại</th></tr></thead><tbody>{report.product_interest.map((product) => <tr key={product.product_id}><th scope="row">{product.product_name}</th><td>{integer(product.impressions)}</td><td>{integer(product.conversations)}</td></tr>)}</tbody></table></div> : <p className="analytics-inline-empty">Chưa có product card nào được hiển thị trong kỳ.</p>}</section>
        </>}
        <p className="analytics-note">Cohort gồm hội thoại có tin nhắn đến trong kỳ. Dữ liệu không có mẫu được hiển thị là “Chưa có dữ liệu”, không chuyển thành 0.</p>
      </>}
    </>}
  </>;
}
