"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useTransition } from "react";

import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";
import { TaskTimeline } from "@/components/task-timeline";
import { createSummaryTask, fetchDocument } from "@/lib/api";
import type { DocumentSummary, TaskStatusResponse } from "@/lib/types";

const ANALYSIS_ROLES = [
  { name: "Chief Lobster", tagline: "任務調度", status: "running", quote: "我會把單文件摘要任務交給最合適的角色。" },
  { name: "Search Lobster", tagline: "資料定位", status: "ready", quote: "摘要前我會先把文件與來源片段定位好。" },
  { name: "Organize Lobster", tagline: "摘要整理", status: "ready", quote: "我會輸出摘要、重點、待辦與引用片段。" },
  { name: "Analyze Lobster", tagline: "多文件分析", status: "upcoming", quote: "差異比較與歸因分析先保留版位，Phase 2 啟用。" },
  { name: "Report Lobster", tagline: "報告輸出", status: "pending", quote: "摘要完成後，Report Lobster 會在報告頁接棒。" }
];

function AnalysisPageContent() {
  // 分析頁以 query string 的 documentId 當入口，讓搜索頁可直接導過來。
  const searchParams = useSearchParams();
  const documentId = searchParams.get("documentId") ?? "";

  const [document, setDocument] = useState<DocumentSummary | null>(null);
  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!documentId) {
      return;
    }

    startTransition(async () => {
      try {
        setDocument(await fetchDocument(documentId));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入文件");
      }
    });
  }, [documentId, startTransition]);

  async function runSummary() {
    // 單文件摘要以同步任務完成，但仍會保存完整的 task/event 狀態。
    if (!documentId) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        setTask(await createSummaryTask(documentId));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "摘要任務失敗");
      }
    });
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
      <RoleSquad roles={ANALYSIS_ROLES} />

      <section className="space-y-5">
        <PixelCard title="單文件摘要工作區" eyebrow="Analysis">
          {document ? (
            <div className="space-y-4">
              <div className="border-4 border-ink bg-sand p-4">
                <h2 className="text-lg font-black tracking-[0.08em]">{document.filename}</h2>
                <p className="mt-2 text-sm text-slate-600">{document.relative_path}</p>
              </div>
              <pre className="pixel-scrollbar max-h-[320px] overflow-auto border-4 border-ink bg-white p-4 text-sm leading-6 whitespace-pre-wrap">
                {document.extracted_text}
              </pre>
              <button
                type="button"
                onClick={runSummary}
                disabled={isPending}
                className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "摘要中..." : "生成摘要"}
              </button>
            </div>
          ) : (
            <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
              從搜索頁選擇文件後，這裡會載入摘要工作區。
            </div>
          )}
        </PixelCard>

        <PixelCard title="摘要結果" eyebrow="Output">
          {task?.result_payload ? (
            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h3 className="text-sm font-black tracking-[0.08em]">摘要</h3>
                <p className="mt-3 text-sm leading-7">{task.result_payload.summary}</p>
              </article>
              <article className="grid gap-4 lg:grid-cols-2">
                <div className="border-4 border-ink bg-white p-4">
                  <h3 className="text-sm font-black tracking-[0.08em]">重點</h3>
                  <ul className="mt-3 space-y-2 text-sm leading-7">
                    {task.result_payload.highlights.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </div>
                <div className="border-4 border-ink bg-white p-4">
                  <h3 className="text-sm font-black tracking-[0.08em]">待辦</h3>
                  <ul className="mt-3 space-y-2 text-sm leading-7">
                    {task.result_payload.todos.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </div>
              </article>
              <Link
                href={`/report?taskId=${task.id}`}
                className="pixel-button inline-flex bg-teal px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
              >
                前往報告頁
              </Link>
            </div>
          ) : (
            <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
              {error || "尚未產生摘要結果。"}
            </div>
          )}
        </PixelCard>

        <PixelCard title="Phase 2 版位預留" eyebrow="Upcoming">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
              多文件差異比較、趨勢摘要、問題歸因與風險提示會沿用這個版面擴充。
            </div>
            <div className="border-4 border-ink bg-sand p-4 text-sm leading-7 text-slate-700">
              目前先保留畫面結構，避免 Phase 2 重新設計工作台骨架。
            </div>
          </div>
        </PixelCard>
      </section>

      <TaskTimeline events={task?.events ?? []} />
    </div>
  );
}

export default function AnalysisPage() {
  // 將使用 search params 的內容包在 Suspense 內，符合 App Router 的 build 要求。
  return (
    <Suspense
      fallback={
        <div className="pixel-panel rounded-none p-6 text-sm text-slate-600">正在載入分析工作台...</div>
      }
    >
      <AnalysisPageContent />
    </Suspense>
  );
}
