import {
  Bot,
  BriefcaseBusiness,
  CalendarDays,
  Headphones,
  HeartHandshake,
  MessageCircle,
  ShoppingBag,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import type { AgentIcon } from "@/lib/api";

export const AGENT_GLYPH_COLOR = "#FFFFFF";

export const AGENT_ICON_OPTIONS: ReadonlyArray<{ key: AgentIcon; label: string }> = [
  { key: "message-circle", label: "Trò chuyện" },
  { key: "bot", label: "Trợ lý AI" },
  { key: "headphones", label: "Hỗ trợ" },
  { key: "sparkles", label: "Sáng tạo" },
  { key: "shopping-bag", label: "Bán hàng" },
  { key: "calendar-days", label: "Đặt lịch" },
  { key: "briefcase-business", label: "Công việc" },
  { key: "heart-handshake", label: "Chăm sóc" },
];

const AGENT_ICONS: Record<AgentIcon, LucideIcon> = {
  "message-circle": MessageCircle,
  bot: Bot,
  headphones: Headphones,
  sparkles: Sparkles,
  "shopping-bag": ShoppingBag,
  "calendar-days": CalendarDays,
  "briefcase-business": BriefcaseBusiness,
  "heart-handshake": HeartHandshake,
};

export function AgentGlyph({ icon, size = 20 }: { icon: AgentIcon; size?: number }) {
  const Icon = AGENT_ICONS[icon];
  return <Icon aria-hidden="true" size={size} strokeWidth={2.2} />;
}
