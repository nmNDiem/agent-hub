import {
  Bot,
  Boxes,
  ChevronDown,
  CircleGauge,
  Menu,
  MessageSquareText,
  Settings,
  Sparkles,
} from "lucide-react";
import type { ReactNode } from "react";

const navigation = [
  { label: "Tổng quan", icon: CircleGauge, active: true },
  { label: "Hội thoại", icon: MessageSquareText },
  { label: "Chatbot", icon: Bot },
  { label: "Sản phẩm", icon: Boxes },
];

function Navigation() {
  return (
    <nav aria-label="Điều hướng chính" className="navigation">
      {navigation.map(({ label, icon: Icon, active }) => (
        <span aria-current={active ? "page" : undefined} className="nav-item" key={label}>
          <Icon aria-hidden="true" size={19} />
          <span>{label}</span>
          {!active && <small>Sắp triển khai</small>}
        </span>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Đi tới nội dung chính
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Sparkles size={19} />
          </span>
          <span>
            <strong>AgentHub</strong>
            <small>AI cho cửa hàng thời trang</small>
          </span>
        </div>
        <Navigation />
        <div className="sidebar-footer">
          <Settings aria-hidden="true" size={19} />
          <span>Cài đặt</span>
          <small>Sắp triển khai</small>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <details className="mobile-navigation">
            <summary aria-label="Mở điều hướng">
              <Menu aria-hidden="true" size={22} />
            </summary>
            <div className="mobile-navigation-panel">
              <Navigation />
            </div>
          </details>
          <div className="shop-placeholder" aria-label="Ngữ cảnh cửa hàng chưa được cấu hình">
            <span className="shop-icon" aria-hidden="true">A</span>
            <span>Cửa hàng chưa thiết lập</span>
            <ChevronDown aria-hidden="true" size={17} />
          </div>
          <span className="phase-badge">F0 · Nền tảng</span>
        </header>
        <main id="main-content" className="content">{children}</main>
      </div>
    </div>
  );
}
