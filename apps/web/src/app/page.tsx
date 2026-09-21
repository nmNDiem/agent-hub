import { Activity, ArrowRight, CheckCircle2, Database, LayoutDashboard } from "lucide-react";

import { AppShell } from "@/components/app-shell";

export const dynamic = "force-dynamic";

type ApiState = "online" | "offline";

async function getApiState(): Promise<ApiState> {
  const baseUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${baseUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(1200),
    });
    return response.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}

export default async function Home() {
  const apiState = await getApiState();

  return (
    <AppShell>
      <section className="page-heading">
        <div>
          <p className="eyebrow">AgentHub · Giai đoạn F0</p>
          <h1>Tổng quan</h1>
          <p>Nền tảng kỹ thuật đã sẵn sàng để phát triển các chức năng trong những phase tiếp theo.</p>
        </div>
        <span className="scaffold-label">Bản scaffold nội bộ</span>
      </section>

      <section aria-labelledby="foundation-title" className="foundation-card" id="foundation">
        <div className="foundation-copy">
          <span className="feature-icon"><LayoutDashboard aria-hidden="true" size={24} /></span>
          <p className="eyebrow">Khởi đầu có kiểm soát</p>
          <h2 id="foundation-title">Chưa có dữ liệu cửa hàng</h2>
          <p>
            F0 chỉ thiết lập ứng dụng, kiểm thử và migration harness. Đăng nhập, sản phẩm,
            tri thức và chatbot sẽ được mở theo đúng roadmap sau khi hoàn tất từng gate.
          </p>
          <a href="#readiness">
            Xem trạng thái nền tảng <ArrowRight aria-hidden="true" size={17} />
          </a>
        </div>
        <div className="foundation-visual" aria-hidden="true">
          <span className="visual-orbit orbit-one" />
          <span className="visual-orbit orbit-two" />
          <SparkleMark />
        </div>
      </section>

      <section aria-labelledby="readiness-title" id="readiness">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Kiểm chứng được</p>
            <h2 id="readiness-title">Trạng thái nền tảng</h2>
          </div>
          <p>Không sử dụng số liệu kinh doanh hoặc trạng thái kết nối mô phỏng.</p>
        </div>
        <div className="status-grid">
          <StatusCard
            icon={<Activity size={21} />}
            label="FastAPI health"
            state={apiState === "online" ? "Đang hoạt động" : "Chưa kết nối"}
            tone={apiState === "online" ? "success" : "neutral"}
            detail={apiState === "online" ? "Phản hồi thật từ /health" : "Khởi động API để kiểm tra"}
          />
          <StatusCard
            icon={<CheckCircle2 size={21} />}
            label="Giao diện quản trị"
            state="Đã dựng scaffold"
            tone="success"
            detail="Responsive, semantic và không có dữ liệu giả"
          />
          <StatusCard
            icon={<Database size={21} />}
            label="Migration"
            state="Đã cấu hình"
            tone="success"
            detail="Baseline rỗng; chưa tạo bảng nghiệp vụ"
          />
        </div>
      </section>
    </AppShell>
  );
}

function StatusCard({ icon, label, state, detail, tone }: {
  icon: React.ReactNode;
  label: string;
  state: string;
  detail: string;
  tone: "success" | "neutral";
}) {
  return (
    <article className="status-card">
      <span className="status-icon" aria-hidden="true">{icon}</span>
      <div>
        <p>{label}</p>
        <strong>{state}</strong>
        <small>{detail}</small>
      </div>
      <span className={`status-dot ${tone}`} aria-hidden="true" />
    </article>
  );
}

function SparkleMark() {
  return (
    <svg viewBox="0 0 120 120" role="presentation">
      <path d="M60 8c5 27 17 39 44 44-27 5-39 17-44 44-5-27-17-39-44-44 27-5 39-17 44-44Z" />
      <circle cx="95" cy="25" r="7" />
    </svg>
  );
}
