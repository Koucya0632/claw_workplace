"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import { fetchOpenClawInstances, fetchOpenClawOperations } from "@/lib/api";
import type { OpenClawInstanceResponse, OpenClawOperationLogRecord } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const OVERVIEW_ROLES = [
  { name: "Chief Lobster", tagline: "控制面總覽", status: "running", quote: "我會把各 Gateway 的狀態與操作脈絡整理成一眼可懂的面板。" },
  { name: "Ops Lobster", tagline: "健康巡檢", status: "ready", quote: "快照能讓我們先看趨勢，再決定是否深入單一實例。" },
  { name: "Agent Steward", tagline: "Agent 盤點", status: "ready", quote: "我會統整目前 Agent 與 Device 的最新快照數量。" },
  { name: "Hook Runner", tagline: "業務派發", status: "pending", quote: "確認控制面穩定後，就能從 Actions 頁手動發送 Hook。" }
];

export default function OpenClawOverviewPage() {
  // 總覽頁要同時拿 instance 與審計紀錄，因此首次載入會平行抓兩份資料。
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [operations, setOperations] = useState<OpenClawOperationLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      setIsLoading(true);
      try {
        const [instancePayload, operationPayload] = await Promise.all([
          fetchOpenClawInstances(),
          fetchOpenClawOperations(12)
        ]);
        setInstances(instancePayload);
        setOperations(operationPayload);
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw 總覽");
      } finally {
        setIsLoading(false);
      }
    });
  }, [startTransition]);

  const activeCount = instances.filter((instance) => instance.is_active).length;
  const healthyCount = instances.filter((instance) => instance.last_health_status === "healthy").length;
  const cachedAgentCount = instances.reduce((sum, instance) => sum + instance.snapshot_summary.agent_count, 0);
  const cachedDeviceCount = instances.reduce((sum, instance) => sum + instance.snapshot_summary.device_count, 0);

  return (
    <OpenClawPageShell
      title="OpenClaw 管理總覽"
      description="這裡先看目前已接入的 OpenClaw Instance、最近健康檢查與管理操作紀錄，再決定要深入哪個模組。"
      roles={OVERVIEW_ROLES}
    >
      <PixelCard title="控制面摘要" eyebrow="Overview">
        <div className="grid gap-4 md:grid-cols-4">
          <article className="border-4 border-ink bg-coral p-4 text-white">
            <p className="text-[11px] uppercase tracking-[0.22em]">Active Instances</p>
            <p className="mt-3 text-3xl font-black">{activeCount}</p>
            <p className="mt-2 text-sm">目前啟用中的 Gateway 實例</p>
          </article>
          <article className="border-4 border-ink bg-mint p-4 text-ink">
            <p className="text-[11px] uppercase tracking-[0.22em]">Healthy</p>
            <p className="mt-3 text-3xl font-black">{healthyCount}</p>
            <p className="mt-2 text-sm">最近健康檢查成功的實例數</p>
          </article>
          <article className="border-4 border-ink bg-gold p-4 text-ink">
            <p className="text-[11px] uppercase tracking-[0.22em]">Cached Agents</p>
            <p className="mt-3 text-3xl font-black">{cachedAgentCount}</p>
            <p className="mt-2 text-sm">依快照統計的 Agent 數量</p>
          </article>
          <article className="border-4 border-ink bg-teal p-4 text-white">
            <p className="text-[11px] uppercase tracking-[0.22em]">Cached Devices</p>
            <p className="mt-3 text-3xl font-black">{cachedDeviceCount}</p>
            <p className="mt-2 text-sm">依快照統計的 Device 數量</p>
          </article>
        </div>
      </PixelCard>

      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <PixelCard title="Instance 快照" eyebrow="Instances">
          {error ? (
            <div className="border-4 border-coral bg-coral/10 p-4 text-sm text-coral">{error}</div>
          ) : isLoading ? (
            <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
              正在同步 OpenClaw 狀態...
            </div>
          ) : instances.length === 0 ? (
            <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
              {isPending ? "正在整理最新畫面..." : "尚未建立 OpenClaw Instance，請先前往實例頁新增。"}
            </div>
          ) : (
            <div className="space-y-3">
              {instances.map((instance) => (
                <article key={instance.id} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-black tracking-[0.08em]">{instance.name}</h3>
                      <p className="mt-1 text-xs text-slate-500">{instance.gateway_url}</p>
                    </div>
                    <StatusPill
                      status={instance.last_health_status ?? (instance.is_active ? "pending" : "disabled")}
                    />
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-3 text-sm text-slate-700">
                    <div>最後巡檢：{formatDateTime(instance.last_health_checked_at)}</div>
                    <div>快取 Agents：{instance.snapshot_summary.agent_count}</div>
                    <div>快取 Devices：{instance.snapshot_summary.device_count}</div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </PixelCard>

        <PixelCard title="最近操作紀錄" eyebrow="Audit">
          {operations.length === 0 ? (
            <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
              尚無操作紀錄，建立或操作 Instance 後會在這裡顯示。
            </div>
          ) : (
            <div className="space-y-3">
              {operations.map((operation) => (
                <article key={operation.id} className="border-4 border-ink bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-black tracking-[0.08em]">{operation.operation_type}</p>
                    <StatusPill status={operation.status} />
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    {operation.instance_id ?? "system"} · {formatDateTime(operation.created_at)}
                  </p>
                  <p className="mt-3 text-sm text-slate-700">
                    {operation.error_message ?? "操作完成，詳情可到對應頁面重新整理查看最新狀態。"}
                  </p>
                </article>
              ))}
            </div>
          )}
        </PixelCard>
      </div>
    </OpenClawPageShell>
  );
}
