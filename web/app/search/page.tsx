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
  continueWorkflowToReport,
  createSearchReportWorkflow,
  createWebSearchWorkflow,
  fetchOpenClawInstances,
  fetchSources,
  fetchWorkflowRun,
  fetchWorkflowRuns
} from "@/lib/api";
import type {
  OpenClawInstanceResponse,
  SourceResponse,
  WebSearchOutputFormat,
  WorkflowRunResponse,
  WorkflowType
} from "@/lib/types";

const WEB_OUTPUT_OPTIONS: Array<{ value: WebSearchOutputFormat; label: string }> = [
  { value: "summary", label: "摘要" },
  { value: "bullets", label: "條列" },
  { value: "table", label: "表格" },
  { value: "comparison", label: "比較" }
];

function SearchWorkflowPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const runIdFromUrl = searchParams.get("runId") ?? "";

  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [workflowMode, setWorkflowMode] = useState<WorkflowType>("search_report");

  const [query, setQuery] = useState("");
  const [sourceId, setSourceId] = useState("");

  const [webTopic, setWebTopic] = useState("");
  const [targetUrlsText, setTargetUrlsText] = useState("");
  const [targetSitesText, setTargetSitesText] = useState("");
  const [targetDomainsText, setTargetDomainsText] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [mustIncludeText, setMustIncludeText] = useState("");
  const [mustExcludeText, setMustExcludeText] = useState("");
  const [focusPointsText, setFocusPointsText] = useState("");
  const [webOutputFormat, setWebOutputFormat] = useState<WebSearchOutputFormat>("summary");
  const [includeProjectSources, setIncludeProjectSources] = useState(false);
  const [resultLimit, setResultLimit] = useState(5);

  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("選擇模式後送出查詢，這裡會即時顯示每個 agent 的工作狀態與處理鏈路。");
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
        const runPayload = await fetchWorkflowRuns({
          instanceId: selectedInstanceId,
          workflowType: workflowMode,
          limit: 12
        });
        setRuns(runPayload);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 workflow 歷史");
      }
    });
  }, [selectedInstanceId, workflowMode, startTransition]);

  useEffect(() => {
    if (!runIdFromUrl) {
      return;
    }

    startTransition(async () => {
      try {
        const runPayload = await fetchWorkflowRun(runIdFromUrl);
        setActiveRun(runPayload);
        setWorkflowMode(runPayload.workflow_type);
        setSelectedInstanceId(runPayload.instance_id);
        hydrateFormsFromRun(runPayload, {
          setQuery,
          setSourceId,
          setWebTopic,
          setTargetUrlsText,
          setTargetSitesText,
          setTargetDomainsText,
          setKeywordsText,
          setMustIncludeText,
          setMustExcludeText,
          setFocusPointsText,
          setWebOutputFormat,
          setIncludeProjectSources,
          setResultLimit
        });
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
          setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: workflowMode, limit: 12 }));
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "輪詢 workflow run 失敗");
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [activeRun, selectedInstanceId, workflowMode]);

  async function handleStartWorkflow() {
    setError("");

    if (!selectedInstanceId) {
      setError("請先選擇 Instance。");
      return;
    }

    if (workflowMode === "search_report") {
      if (!query.trim()) {
        setError("請先輸入搜索查詢。");
        return;
      }
      setMessage("已送出搜索-分析-報告工作流，正在啟動搜索 agent。");
    } else {
      if (!webTopic.trim()) {
        setError("請先輸入搜尋內容 / 主題。");
        return;
      }
      setMessage("已送出 Web Search 工作流，正在理解搜尋目標。");
    }

    startTransition(async () => {
      try {
        const runPayload =
          workflowMode === "search_report"
            ? await createSearchReportWorkflow({
                instance_id: selectedInstanceId,
                query: query.trim(),
                source_id: sourceId || undefined
              })
            : await createWebSearchWorkflow({
                instance_id: selectedInstanceId,
                topic: webTopic.trim(),
                target_urls: parseLineList(targetUrlsText),
                target_sites: parseLineList(targetSitesText),
                target_domains: parseLineList(targetDomainsText),
                keywords: parseLineList(keywordsText),
                must_include: parseLineList(mustIncludeText),
                must_exclude: parseLineList(mustExcludeText),
                focus_points: parseLineList(focusPointsText),
                output_format: webOutputFormat,
                include_project_sources: includeProjectSources,
                source_id: includeProjectSources && sourceId ? sourceId : undefined,
                result_limit: resultLimit
              });

        setActiveRun(runPayload);
        setWorkflowMode(runPayload.workflow_type);
        router.replace(`/search?runId=${runPayload.id}`);
        setRuns(await fetchWorkflowRuns({ instanceId: selectedInstanceId, workflowType: runPayload.workflow_type, limit: 12 }));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 workflow run 失敗");
      }
    });
  }

  async function handleSelectRun(runId: string) {
    try {
      const runPayload = await fetchWorkflowRun(runId);
      setActiveRun(runPayload);
      setWorkflowMode(runPayload.workflow_type);
      hydrateFormsFromRun(runPayload, {
        setQuery,
        setSourceId,
        setWebTopic,
        setTargetUrlsText,
        setTargetSitesText,
        setTargetDomainsText,
        setKeywordsText,
        setMustIncludeText,
        setMustExcludeText,
        setFocusPointsText,
        setWebOutputFormat,
        setIncludeProjectSources,
        setResultLimit
      });
      router.replace(`/search?runId=${runId}`);
      setMessage("已切換到指定 workflow run。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "無法切換 workflow run");
    }
  }

  async function handleContinueToReport() {
    if (!activeRun || activeRun.workflow_type !== "web_search") {
      return;
    }

    setError("");
    setMessage("已收到接續要求，正在建立分析/報告流程。");

    startTransition(async () => {
      try {
        const nextRun = await continueWorkflowToReport(activeRun.id);
        setActiveRun(nextRun);
        setWorkflowMode(nextRun.workflow_type);
        router.replace(`/search?runId=${nextRun.id}`);
        setRuns(await fetchWorkflowRuns({ instanceId: nextRun.instance_id, workflowType: nextRun.workflow_type, limit: 12 }));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立接續 workflow 失敗");
      }
    });
  }

  function handleExportMarkdown() {
    const markdown = activeRun?.final_report?.markdown ?? activeRun?.final_web_result?.markdown;
    if (!markdown || !activeRun) {
      return;
    }

    const title = activeRun.final_report?.title ?? activeRun.final_web_result?.title ?? activeRun.id;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function handleModeChange(nextMode: WorkflowType) {
    setWorkflowMode(nextMode);
    setActiveRun(null);
    setError("");
    setMessage(
      nextMode === "search_report"
        ? "已切回搜索-分析-報告模式。"
        : "已切到 Web Search 模式，可自訂網址、網站、網域、關鍵字與輸出格式。"
    );
    router.replace("/search");
  }

  const workflowRoles = useMemo(() => buildWorkflowRoles(activeRun, workflowMode), [activeRun, workflowMode]);
  const activeModeDescription =
    workflowMode === "search_report"
      ? "把既有專案索引交給三個 agent 串行完成搜索、分析、報告。"
      : "先理解外網搜尋目標，再搜尋、過濾並格式化輸出結果。";

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <RoleSquad roles={workflowRoles} />

      <section className="space-y-5">
        <PixelCard title="搜索工作台" eyebrow="Workflow">
          <div className="flex flex-wrap gap-2">
            <ModeButton
              label="Project Workflow"
              active={workflowMode === "search_report"}
              description="搜索 / 分析 / 報告"
              onClick={() => handleModeChange("search_report")}
            />
            <ModeButton
              label="Web Search"
              active={workflowMode === "web_search"}
              description="理解 / 搜尋 / 過濾 / 輸出"
              onClick={() => handleModeChange("web_search")}
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
            <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
            <div className="border-4 border-ink bg-white px-4 py-3 text-sm text-slate-700">
              <p className="font-black tracking-[0.08em]">{workflowMode === "search_report" ? "Project Workflow" : "Web Search"}</p>
              <p className="mt-2 leading-7">{activeModeDescription}</p>
            </div>
          </div>

          {workflowMode === "search_report" ? (
            <div className="mt-4 grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_auto]">
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
          ) : (
            <div className="mt-4 space-y-4">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                <textarea
                  value={webTopic}
                  onChange={(event) => setWebTopic(event.target.value)}
                  placeholder="搜尋內容 / 主題"
                  rows={3}
                  className="border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
                />
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">回傳格式</span>
                    <select
                      value={webOutputFormat}
                      onChange={(event) => setWebOutputFormat(event.target.value as WebSearchOutputFormat)}
                      className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
                    >
                      {WEB_OUTPUT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">結果筆數</span>
                    <select
                      value={String(resultLimit)}
                      onChange={(event) => setResultLimit(Number(event.target.value))}
                      className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
                    >
                      {[3, 5, 8, 10].map((limit) => (
                        <option key={limit} value={limit}>
                          {limit} 筆
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
                    <input
                      type="checkbox"
                      checked={includeProjectSources}
                      onChange={(event) => setIncludeProjectSources(event.target.checked)}
                      className="h-4 w-4"
                    />
                    <span className="text-sm font-black tracking-[0.08em]">合併專案索引結果</span>
                  </label>
                  <button
                    type="button"
                    onClick={handleStartWorkflow}
                    disabled={!selectedInstanceId || !webTopic.trim() || isPending}
                    className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
                  >
                    {isPending ? "啟動中..." : "啟動 Web Search"}
                  </button>
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-3">
                <WorkflowTextAreaField
                  label="指定搜尋網址"
                  value={targetUrlsText}
                  onChange={setTargetUrlsText}
                  placeholder="每行一個 URL"
                />
                <WorkflowTextAreaField
                  label="指定搜尋網站"
                  value={targetSitesText}
                  onChange={setTargetSitesText}
                  placeholder="每行一個網站名稱"
                />
                <WorkflowTextAreaField
                  label="指定搜尋網域"
                  value={targetDomainsText}
                  onChange={setTargetDomainsText}
                  placeholder="每行一個網域，例如 example.com"
                />
                <WorkflowTextAreaField
                  label="搜尋關鍵字"
                  value={keywordsText}
                  onChange={setKeywordsText}
                  placeholder="每行一個關鍵字"
                />
                <WorkflowTextAreaField
                  label="必須包含"
                  value={mustIncludeText}
                  onChange={setMustIncludeText}
                  placeholder="每行一個必要條件"
                />
                <WorkflowTextAreaField
                  label="必須排除"
                  value={mustExcludeText}
                  onChange={setMustExcludeText}
                  placeholder="每行一個排除條件"
                />
              </div>

              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
                <WorkflowTextAreaField
                  label="需要重點整理的資訊"
                  value={focusPointsText}
                  onChange={setFocusPointsText}
                  placeholder="例如：價格差異、風險、優缺點、官方說法"
                />
                <label className="space-y-2">
                  <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">專案資料源篩選</span>
                  <select
                    value={sourceId}
                    onChange={(event) => setSourceId(event.target.value)}
                    disabled={!includeProjectSources}
                    className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none disabled:bg-slate-100"
                  >
                    <option value="">全部資料源</option>
                    {sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )}

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

        <WorkflowReportPanel
          run={activeRun}
          onExportMarkdown={handleExportMarkdown}
          onContinueToReport={activeRun?.workflow_type === "web_search" && activeRun.status === "completed" ? handleContinueToReport : undefined}
          continueDisabled={isPending}
        />
      </section>
    </div>
  );
}

function buildWorkflowRoles(activeRun: WorkflowRunResponse | null, workflowMode: WorkflowType) {
  const activeType = activeRun?.workflow_type ?? workflowMode;
  const stageStatusMap = new Map((activeRun?.stages ?? []).map((stage) => [stage.stage_key, stage.status]));
  const stageAgentMap = new Map((activeRun?.stages ?? []).map((stage) => [stage.stage_key, stage.agent_id]));

  if (activeType === "web_search") {
    return [
      {
        name: "Intent Agent",
        tagline: stageAgentMap.get("understand") ?? "待配置",
        status: stageStatusMap.get("understand") ?? "pending",
        quote: "我會先理解搜尋主題、關鍵字、網址與輸出格式。"
      },
      {
        name: "Search Agent",
        tagline: stageAgentMap.get("search") ?? "待配置",
        status: stageStatusMap.get("search") ?? "pending",
        quote: "我會根據條件搜尋外部網站，必要時再補入專案索引內容。"
      },
      {
        name: "Filter Agent",
        tagline: stageAgentMap.get("filter") ?? "待配置",
        status: stageStatusMap.get("filter") ?? "pending",
        quote: "我會剔除噪音、保留真正相關的來源與重點。"
      },
      {
        name: "Format Agent",
        tagline: stageAgentMap.get("format") ?? "待配置",
        status: stageStatusMap.get("format") ?? "pending",
        quote: "我會把結果整理成摘要、條列、表格或比較格式。"
      }
    ];
  }

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

function hydrateFormsFromRun(
  run: WorkflowRunResponse,
  setters: {
    setQuery: (value: string) => void;
    setSourceId: (value: string) => void;
    setWebTopic: (value: string) => void;
    setTargetUrlsText: (value: string) => void;
    setTargetSitesText: (value: string) => void;
    setTargetDomainsText: (value: string) => void;
    setKeywordsText: (value: string) => void;
    setMustIncludeText: (value: string) => void;
    setMustExcludeText: (value: string) => void;
    setFocusPointsText: (value: string) => void;
    setWebOutputFormat: (value: WebSearchOutputFormat) => void;
    setIncludeProjectSources: (value: boolean) => void;
    setResultLimit: (value: number) => void;
  }
) {
  if (run.workflow_type === "web_search") {
    setters.setWebTopic(String(run.input_payload.topic ?? ""));
    setters.setTargetUrlsText(joinList(run.input_payload.target_urls));
    setters.setTargetSitesText(joinList(run.input_payload.target_sites));
    setters.setTargetDomainsText(joinList(run.input_payload.target_domains));
    setters.setKeywordsText(joinList(run.input_payload.keywords));
    setters.setMustIncludeText(joinList(run.input_payload.must_include));
    setters.setMustExcludeText(joinList(run.input_payload.must_exclude));
    setters.setFocusPointsText(joinList(run.input_payload.focus_points));
    setters.setWebOutputFormat((run.input_payload.output_format as WebSearchOutputFormat) ?? "summary");
    setters.setIncludeProjectSources(Boolean(run.input_payload.include_project_sources));
    setters.setResultLimit(Number(run.input_payload.result_limit ?? 5));
    setters.setSourceId(String(run.input_payload.source_id ?? ""));
    return;
  }

  setters.setQuery(String(run.input_payload.query ?? ""));
  setters.setSourceId(String(run.input_payload.source_id ?? ""));
}

function parseLineList(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).join("\n") : "";
}

function ModeButton({
  label,
  description,
  active,
  onClick
}: {
  label: string;
  description: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border-4 border-ink px-4 py-3 text-left transition ${active ? "bg-ink text-sand" : "bg-white text-ink"}`}
    >
      <p className="text-sm font-black tracking-[0.08em]">{label}</p>
      <p className={`mt-1 text-xs ${active ? "text-sand/80" : "text-slate-500"}`}>{description}</p>
    </button>
  );
}

function WorkflowTextAreaField({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string;
  value: string;
  onChange: (nextValue: string) => void;
  placeholder: string;
}) {
  return (
    <label className="space-y-2">
      <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={4}
        className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
      />
    </label>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="pixel-panel rounded-none p-6 text-sm text-slate-600">正在載入工作流頁面...</div>}>
      <SearchWorkflowPageContent />
    </Suspense>
  );
}
