"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { fetchOpenClawInstances, fetchOpenClawLogs } from "@/lib/api";
import type { OpenClawInstanceResponse, OpenClawLogEntry } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const LOG_ROLES = [
  { name: "Chief Lobster", tagline: "日誌巡航", status: "running", quote: "先把 limit 與 instance 定好，再拉出可讀的 Gateway logs。" },
  { name: "Log Watcher", tagline: "錯誤定位", status: "ready", quote: "Phase 1 先做手動 refresh，讓日誌頁保持簡單而穩定。" },
  { name: "Context Keeper", tagline: "操作脈絡", status: "pending", quote: "若要追連續事件，先去總覽看審計紀錄，再回來對照原始 logs。" }
];

export default function OpenClawLogsPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [limit, setLimit] = useState(100);
  const [logs, setLogs] = useState<OpenClawLogEntry[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();
  const hasInstances = instances.length > 0;
  const canViewLogs = Boolean(selectedInstanceId);

  async function loadLogs(instanceId: string, nextLimit: number) {
    if (!instanceId) {
      setLogs([]);
      return;
    }
    setLogs(await fetchOpenClawLogs(instanceId, nextLimit));
  }

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        const nextInstanceId = instancePayload[0]?.id ?? "";
        setSelectedInstanceId(nextInstanceId);
        if (nextInstanceId) {
          await loadLogs(nextInstanceId, limit);
          setMessage("limit 建議先維持在 100~200，避免畫面一次塞太多內容。");
        } else {
          setLogs([]);
          setMessage("先建立 OpenClaw Instance，這裡才能查看 Gateway logs。");
        }
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Logs");
      }
    });
  }, [limit, startTransition]);

  useEffect(() => {
    if (!selectedInstanceId) {
      setLogs([]);
      return;
    }

    startTransition(async () => {
      try {
        await loadLogs(selectedInstanceId, limit);
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法切換 Logs 清單");
      }
    });
  }, [limit, selectedInstanceId, startTransition]);

  return (
    <OpenClawPageShell
      title="Logs"
      description="Logs 是 OpenClaw Control Center 內的 Admin Tools 分區，提供手動 refresh 與 limit 控制，方便在不建立長連線的前提下查看 Gateway 日誌。"
      roles={LOG_ROLES}
      sectionGroup="Admin Tools"
      sectionLabel="Logs"
    >
      <PixelCard title="Logs 查詢" eyebrow="Logs">
        <div className="grid gap-4 lg:grid-cols-[280px_140px_auto_1fr]">
          <OpenClawInstancePicker
            instances={instances}
            value={selectedInstanceId}
            onChange={setSelectedInstanceId}
            disabled={!hasInstances || isPending}
          />
          <input
            value={String(limit)}
            onChange={(event) => setLimit(Number(event.target.value || 100))}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            type="number"
            min={1}
            max={500}
          />
          <button
            type="button"
            onClick={() => selectedInstanceId && loadLogs(selectedInstanceId, limit)}
            disabled={!canViewLogs || isPending}
            className="pixel-button bg-teal px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
          >
            重新整理
          </button>
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message || "limit 建議先維持在 100~200，避免畫面一次塞太多內容。"}
          </div>
        </div>
      </PixelCard>

      <PixelCard title="日誌內容" eyebrow="Gateway Logs">
        {logs.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            {isPending ? "正在同步 Gateway logs..." : "目前沒有可顯示的 logs。"}
          </div>
        ) : (
          <div className="space-y-3">
            {logs.map((entry, index) => (
              <article key={`${entry.timestamp ?? "log"}-${index}`} className="border-4 border-ink bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{entry.level ?? "info"}</p>
                  <p className="text-xs text-slate-500">{entry.timestamp ? formatDateTime(entry.timestamp) : "未提供時間"}</p>
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-700">{entry.message}</p>
              </article>
            ))}
          </div>
        )}
      </PixelCard>
    </OpenClawPageShell>
  );
}
