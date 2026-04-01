"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useTransition } from "react";

import { PixelCard } from "@/components/pixel-card";
import { ReportPreview } from "@/components/report-preview";
import { RoleSquad } from "@/components/role-squad";
import { exportMarkdownReport, fetchTask } from "@/lib/api";
import type { TaskStatusResponse } from "@/lib/types";

const REPORT_ROLES = [
  { name: "Chief Lobster", tagline: "整合結果", status: "ready", quote: "我會把摘要任務的最終輸出交給報告頁。" },
  { name: "Search Lobster", tagline: "來源證據", status: "completed", quote: "引用片段已附在摘要結果中。" },
  { name: "Organize Lobster", tagline: "內容整理", status: "completed", quote: "重點、待辦與摘要已完成整理。" },
  { name: "Analyze Lobster", tagline: "後續分析", status: "upcoming", quote: "未來這裡會增加異常、歸因與風險說明。" },
  { name: "Report Lobster", tagline: "Markdown 匯出", status: "ready", quote: "我會把摘要結果格式化成可交付 Markdown。" }
];

function ReportPageContent() {
  // 報告頁依賴 taskId，所以會從 query string 讀取並抓取任務詳情。
  const searchParams = useSearchParams();
  const taskId = searchParams.get("taskId") ?? "";

  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!taskId) {
      return;
    }

    startTransition(async () => {
      try {
        setTask(await fetchTask(taskId));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入任務");
      }
    });
  }, [taskId, startTransition]);

  async function handleExport() {
    // 匯出時直接向後端索取 Markdown，再由瀏覽器建立下載檔案。
    if (!taskId) {
      return;
    }

    try {
      const payload = await exportMarkdownReport(taskId);
      const blob = new Blob([payload.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = payload.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "匯出失敗");
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <RoleSquad roles={REPORT_ROLES} />

      <section className="space-y-5">
        <PixelCard title="報告輸出面板" eyebrow="Report">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
            <div className="border-4 border-ink bg-sand p-4 text-sm leading-7 text-slate-700">
              {task?.result_payload?.summary ?? "請從分析頁完成摘要任務，然後帶著 taskId 來到此頁。"}
            </div>
            <button
              type="button"
              onClick={handleExport}
              disabled={!task?.result_payload || isPending}
              className="pixel-button h-fit bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              匯出 Markdown
            </button>
          </div>
          {error ? <p className="mt-4 text-sm text-coral">{error}</p> : null}
        </PixelCard>

        <ReportPreview task={task} />
      </section>
    </div>
  );
}

export default function ReportPage() {
  // 報告頁同樣依賴 search params，因此以 Suspense 邊界包住客戶端內容。
  return (
    <Suspense
      fallback={
        <div className="pixel-panel rounded-none p-6 text-sm text-slate-600">正在載入報告面板...</div>
      }
    >
      <ReportPageContent />
    </Suspense>
  );
}
