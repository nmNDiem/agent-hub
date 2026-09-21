import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AgentHub",
  description: "Nền tảng trợ lý AI đa kênh cho cửa hàng",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
