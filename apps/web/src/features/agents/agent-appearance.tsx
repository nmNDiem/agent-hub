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

export function agentGlyphColor(background: string): "#FFFFFF" | "#14181F" {
  if (!/^#[0-9A-Fa-f]{6}$/.test(background)) return "#FFFFFF";
  const channels = [1, 3, 5].map((offset) => Number.parseInt(background.slice(offset, offset + 2), 16))
    .map((channel) => {
      const normalized = channel / 255;
      return normalized <= 0.04045
        ? normalized / 12.92
        : ((normalized + 0.055) / 1.055) ** 2.4;
    });
  const luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  const whiteContrast = 1.05 / (luminance + 0.05);
  const darkContrast = (luminance + 0.05) / 0.05;
  return whiteContrast >= darkContrast ? "#FFFFFF" : "#14181F";
}
