import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Navigation } from "@/components/navigation";

import "./globals.css";

export const metadata: Metadata = {
  title: "OpenClaw 智能辦公室",
  description: "Phase 1 本地優先智能辦公室工作台"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // layout 會固定導覽列與整體背景，讓各頁共享同一個像素工作台外框。
  return (
    <html lang="zh-Hant">
      <body>
        <main className="mx-auto flex min-h-screen max-w-[1680px] flex-col gap-5 px-4 py-4 md:px-6 md:py-5">
          <Navigation />
          {children}
        </main>
      </body>
    </html>
  );
}
