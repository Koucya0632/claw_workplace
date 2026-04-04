"use client";

import { Suspense, useEffect, useMemo, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";
import { StatusPill } from "@/components/status-pill";
import { WorkflowEventTimeline } from "@/components/workflow-event-timeline";
import { WorkflowReportPanel } from "@/components/workflow-report-panel";
import { WorkflowRunList } from "@/components/workflow-run-list";
import { WorkflowStageBoard } from "@/components/workflow-stage-board";
import {
  createSearchReportWorkflow,
  fetchOpenClawInstances,
  fetchSources,
  fetchWorkflowRun,
  fetchWorkflowRuns
} from "@/lib/api";
import type { OpenClawInstanceResponse, SourceResponse, WorkflowRunResponse } from "@/lib/types";

function SearchWorkflowPageContent() {
  // 新版 /search 直接成為搜索-分析-報告的一體化主入口，因此會同時管理查詢、run、輪詢與歷史紀錄。
  const router = useRouter();
  const searchParams = useSearchParams();
  const runIdFromUrl = searchParams.get("runId") ?? "";

  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [query, setQuery] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("先指定 Instance、輸入查詢，再讓三階段 agent 自動接棒。");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const [sourcePayload, instancePayload] = await Promise.all([fetchSources(), fetchOpenClawInstances()]);
        setSources(sourcePayload);
        setInstances(instancePayload);
        if (instancePayload.length > 0) {
          setSelectedInstanceId((current) => current || instancePayload[0].id);
        }
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入搜索工作台初始化資料");
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!selectedInstanceId) {
      setRuns([]);
      return;
    }

    startTransition(async () => {
      try {
        const runPayload = await fetchWorkflowRuns({ instanceId: selectedInstanceId, limit: 12 });
        setRuns(runPayload);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 workflow 歷史");
      }
    });
  }, [selectedInstanceId, startTransition]);

  useEffect(() => {
    if (!runIdFromUrl) {
      return;
    }

    startTransition(async () => {
      try {
        const runPayload = await fetchWorkflowRun(runIdFromUrl);
        setActiveRun(runPayload);
        setSelectedInstanceId(runPayload.instance_id);
        setQuery(String(runPayload.input_payload.query ?? ""));
        setSourceId(String(runPayload.input_payload.source_id ?? ""));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入指定 workflow run");
      }
    });
  }, [runIdFromUrl, startTransition]);

  useEffect(() => {
    if (!activeRun || !["pending", "running"].includes(activeRun.status)) {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextRun = await fetchWorkflowRun(activeRun.id);
        setActiveRun(nextRun);
        if (selectedInstanceId) {
          setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, limit: 12 }));
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "輪詢 workflow run 失敗");
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [activeRun, selectedInstanceId]);

  async function handleStartWorkflow() {
    if (!selectedInstanceId || !query.trim()) {
      setError("請先選擇 Instance，並輸入搜索查詢。");
      return;
    }

    setError("");
    setMessage("已送出工作流，正在啟動搜索 agent。");

    startTransition(async () => {
      try {
        const runPayload = await createSearchReportWorkflow({
          instance_id: selectedInstanceId,
          query: query.trim(),
          source_id: sourceId || undefined
        });
        setActiveRun(runPayload);
        router.replace(`/search?runId=${runPayload.id}`);
        setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, limit: 12 }));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 workflow run 失敗");
      }
    });
  }

  async function handleSelectRun(runId: string) {
    try {
      const runPayload = await fetchWorkflowRun(runId);
      setActiveRun(runPayload);
      router.replace(`/search?runId=${runId}`);
      setMessage("已切換到指定 workflow run。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "無法切換 workflow run");
    }
  }

  function handleExportMarkdown() {
    if (!activeRun?.final_report) {
      return;
    }

    const blob = new Blob([activeRun.final_report.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${activeRun.final_report.title || activeRun.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const workflowRoles = useMemo(() => buildWorkflowRoles(activeRun), [activeRun]);

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <RoleSquad roles={workflowRoles} />

      <section className="space-y-5">
        <PixelCard title="搜索-分析-報告工作台" eyebrow="Workflow">
          <div className="grid gap-4 xl:grid-cols-[220px_220px_minmax(0,1fr)_auto]">
            <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
            <select
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            >
              <option value="">全部資料源</option>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="輸入要交給搜索 agent 的查詢"
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
            <button
              type="button"
              onClick={handleStartWorkflow}
              disabled={!selectedInstanceId || !query.trim() || isPending}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
            >
              {isPending ? "啟動中..." : "啟動流程"}
            </button>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_280px]">
            <div className="border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
              {error ? <span className="text-coral">{error}</span> : message}
            </div>
            <div className="border-4 border-ink bg-sand p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">整體進度</p>
                  <p className="mt-1 text-lg font-black">{activeRun?.overall_progress_percent ?? 0}%</p>
                </div>
                <StatusPill status={activeRun?.status ?? "pending"} />
              </div>
              <div className="mt-3 h-4 border-2 border-ink bg-slate-100">
                <div
                  className="h-full bg-teal transition-[width]"
                  style={{ width: `${Math.max(0, Math.min(100, activeRun?.overall_progress_percent ?? 0))}%` }}
                />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">
                {activeRun
                  ? `目前進行到 ${activeRun.current_stage ?? "等待啟動"}，處理 agent：${activeRun.active_agent_id ?? "尚未指派"}`
                  : "送出查詢後，這裡會顯示目前進行到哪一步。"}
              </p>
            </div>
          </div>
        </PixelCard>

        <WorkflowStageBoard run={activeRun} />

        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <WorkflowRunList runs={runs} activeRunId={activeRun?.id} onSelect={handleSelectRun} />
          <WorkflowEventTimeline events={activeRun?.events ?? []} />
        </div>

        <WorkflowReportPanel run={activeRun} onExportMarkdown={handleExportMarkdown} />
      </section>
    </div>
  );
}

function buildWorkflowRoles(activeRun: WorkflowRunResponse | null) {
  // 左側角色欄雖然不是主資訊，但會即時反映目前哪個階段最活躍，補強整體可視化節奏。
  const stageStatusMap = new Map((activeRun?.stages ?? []).map((stage) => [stage.stage_key, stage.status]));
  const stageAgentMap = new Map((activeRun?.stages ?? []).map((stage) => [stage.stage_key, stage.agent_id]));

  return [
    {
      name: "Search Agent",
      tagline: stageAgentMap.get("search") ?? "待配置",
      status: stageStatusMap.get("search") ?? "pending",
      quote: "我負責先找出最相關來源，並把候選證據整理乾淨。"
    },
    {
      name: "Analysis Agent",
      tagline: stageAgentMap.get("analysis") ?? "待配置",
      status: stageStatusMap.get("analysis") ?? "pending",
      quote: "我會把搜索結果收斂成重點、風險、待辦與證據。"
    },
    {
      name: "Report Agent",
      tagline: stageAgentMap.get("report") ?? "待配置",
      status: stageStatusMap.get("report") ?? "pending",
      quote: "我會把分析成果轉成結構化報告與 Markdown。"
    }
  ];
}

export default function SearchPage() {
  // App Router 下若使用 search params，仍需包在 Suspense 內避免 build 失敗。
  return (
    <Suspense fallback={<div className="pixel-panel rounded-none p-6 text-sm text-slate-600">正在載入工作流頁面...</div>}>
      <SearchWorkflowPageContent />
    </Suspense>
  );
}
