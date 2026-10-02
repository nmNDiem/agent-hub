import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AgentHub",
  description: "Nền tảng trợ lý AI đa kênh cho cửa hàng",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html data-palette="lagoon" data-scroll-behavior="smooth" lang="vi" suppressHydrationWarning><body>{children}</body></html>;
}
