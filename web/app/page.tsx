"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";
import { SourceStatusBoard } from "@/components/source-status-board";
import { fetchSources } from "@/lib/api";
import type { SourceResponse } from "@/lib/types";

const DEFAULT_ROLES = [
  { name: "Chief Lobster", tagline: "任務調度", status: "ready", quote: "我會把任務拆清楚，再交給對的角色。" },
  { name: "Search Lobster", tagline: "資料定位", status: "ready", quote: "本地檔案一旦完成索引，我就能快速定位證據。" },
  { name: "Organize Lobster", tagline: "摘要整理", status: "pending", quote: "我會把重點、待辦與引用片段整理成可交付結果。" },
  { name: "Analyze Lobster", tagline: "多文件分析", status: "upcoming", quote: "Phase 2 我會接手比較、歸因與風險提示。" },
  { name: "Report Lobster", tagline: "報告輸出", status: "upcoming", quote: "目前先輸出 Markdown，之後再擴充更多格式。" }
];

export default function DashboardPage() {
  // 主控台需要展示來源狀態，因此首次載入就抓一次資料。
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [error, setError] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        setSources(await fetchSources());
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入資料源");
      }
    });
  }, [startTransition]);

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
      <RoleSquad roles={DEFAULT_ROLES} />

      <section className="space-y-5">
        <PixelCard title="指揮主控台" eyebrow="Dashboard">
          <div className="grid gap-4 md:grid-cols-3">
            <article className="border-4 border-ink bg-coral p-4 text-white">
              <p className="text-[11px] uppercase tracking-[0.22em]">資料源</p>
              <p className="mt-3 text-3xl font-black">{sources.length}</p>
              <p className="mt-2 text-sm">已建立的本地接入數量</p>
            </article>
            <article className="border-4 border-ink bg-gold p-4 text-ink">
              <p className="text-[11px] uppercase tracking-[0.22em]">搜索能力</p>
              <p className="mt-3 text-3xl font-black">FTS5</p>
              <p className="mt-2 text-sm">支援檔名與全文搜尋</p>
            </article>
            <article className="border-4 border-ink bg-teal p-4 text-white">
              <p className="text-[11px] uppercase tracking-[0.22em]">輸出格式</p>
              <p className="mt-3 text-3xl font-black">MD</p>
              <p className="mt-2 text-sm">摘要任務完成後可直接匯出</p>
            </article>
          </div>
        </PixelCard>

        <PixelCard title="快捷任務" eyebrow="Quick Actions">
          <div className="grid gap-3 md:grid-cols-3">
            <Link href="/settings/sources" className="pixel-button bg-sand p-4 text-left">
              <h3 className="text-sm font-black tracking-[0.08em]">1. 接入本地資料夾</h3>
              <p className="mt-2 text-sm text-slate-600">先建立資料源並執行掃描。</p>
            </Link>
            <Link href="/search" className="pixel-button bg-sand p-4 text-left">
              <h3 className="text-sm font-black tracking-[0.08em]">2. 搜索文件</h3>
              <p className="mt-2 text-sm text-slate-600">依檔名或全文快速找出目標內容。</p>
            </Link>
            <Link href="/analysis" className="pixel-button bg-sand p-4 text-left">
              <h3 className="text-sm font-black tracking-[0.08em]">3. 生成摘要</h3>
              <p className="mt-2 text-sm text-slate-600">對單一文件做摘要、重點與待辦輸出。</p>
            </Link>
          </div>
        </PixelCard>

        <PixelCard title="最近任務" eyebrow="Recent">
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            Phase 1 先以搜尋結果進入摘要任務。完成任務後可從報告頁依 `taskId` 回看結果。
          </div>
        </PixelCard>
      </section>

      <section className="space-y-5">
        <SourceStatusBoard sources={sources} />
        <PixelCard title="系統提示" eyebrow="Status">
          {error ? (
            <div className="border-4 border-coral bg-coral/10 p-4 text-sm text-coral">{error}</div>
          ) : (
            <div className="space-y-3 text-sm leading-7 text-slate-700">
              <p>本頁會顯示目前資料源狀態與工作台入口。</p>
              <p>{isPending ? "正在同步後端狀態..." : "主控台已就緒，可前往設定頁建立本地資料源。"}</p>
            </div>
          )}
        </PixelCard>
      </section>
    </div>
  );
}
