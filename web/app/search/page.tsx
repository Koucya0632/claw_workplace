"use client";

import { Suspense, useEffect, useMemo, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
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
  BusinessType,
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

const BUSINESS_TYPE_OPTIONS: Array<{ value: BusinessType; label: string }> = [
  { value: "support", label: "Support" },
  { value: "product", label: "Product" },
  { value: "engineering", label: "Engineering" },
  { value: "compliance", label: "Compliance" },
  { value: "operations", label: "Operations" },
  { value: "market", label: "Market" },
  { value: "finance", label: "Finance" },
  { value: "security", label: "Security" }
];

const PRIMARY_INSTANCE_ID = "oc_8b451d1865b74e8797df82aaaf1e316f";

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
  const [businessType, setBusinessType] = useState<BusinessType | "">("");
  const [includeProjectSources, setIncludeProjectSources] = useState(false);
  const [resultLimit, setResultLimit] = useState(5);

  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("等待啟動。");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const [sourcePayload, instancePayload] = await Promise.all([fetchSources(), fetchOpenClawInstances()]);
        setSources(sourcePayload);
        setInstances(instancePayload);
        if (instancePayload.length > 0) {
          const preferredInstanceId = instancePayload.some((instance) => instance.id === PRIMARY_INSTANCE_ID)
            ? PRIMARY_INSTANCE_ID
            : instancePayload[0].id;
          setSelectedInstanceId((current) => current || preferredInstanceId);
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
          setBusinessType,
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
      setMessage("已送出 Project Workflow。");
    } else {
      if (!webTopic.trim()) {
        setError("請先輸入搜尋內容 / 主題。");
        return;
      }
      setMessage("已送出 Web Search + Ingest。");
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
                business_type: businessType || undefined,
                auto_publish: true,
                source_merge_hint: webTopic.trim(),
                ingest_mode: "auto_store",
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
        setBusinessType,
        setIncludeProjectSources,
        setResultLimit
      });
      router.replace(`/search?runId=${runId}`);
      setMessage("已切換 workflow run。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "無法切換 workflow run");
    }
  }

  async function handleContinueToReport() {
    if (!activeRun || activeRun.workflow_type !== "web_search") {
      return;
    }

    setError("");
    setMessage("正在建立分析/報告流程。");

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
        ? "已切回 Project Workflow。"
        : "已切到 Web Search + Ingest。"
    );
    router.replace("/search");
  }

  const workflowRoles = useMemo(() => buildWorkflowRoles(activeRun, workflowMode), [activeRun, workflowMode]);
  const activeModeDescription =
    workflowMode === "search_report"
      ? "搜索、分析、報告。"
      : "理解、搜尋、過濾、入庫、輸出。";

  return (
    <div className="space-y-5">
      <section className="page-intro rounded-[1.75rem] px-5 py-5 md:px-6">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-5">
            <div className="space-y-3">
              <p className="text-[10px] uppercase tracking-[0.3em] text-slate-500">Workflow</p>
              <div className="space-y-2">
                <h1 className="pixel-title text-2xl font-black tracking-[0.06em] text-ink md:text-3xl">搜索工作台</h1>
                <p className="max-w-3xl text-sm leading-6 text-slate-700">先啟動，再追蹤，再看結果。</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <ModeButton
                label="Project Workflow"
                active={workflowMode === "search_report"}
                description="搜索 / 分析 / 報告"
                onClick={() => handleModeChange("search_report")}
              />
              <ModeButton
                label="Web Search + Ingest"
                active={workflowMode === "web_search"}
                description="理解 / 搜尋 / 過濾 / 入庫 / 輸出"
                onClick={() => handleModeChange("web_search")}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
              <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
              <div className="rounded-[1.25rem] border border-slate-200 bg-white/90 px-4 py-4 text-sm text-slate-700">
                <p className="font-black tracking-[0.05em]">
                  {workflowMode === "search_report" ? "Project Workflow" : "Web Search + Ingest"}
                </p>
                <p className="mt-2 leading-6">{activeModeDescription}</p>
              </div>
            </div>

            {workflowMode === "search_report" ? (
              <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_auto]">
                <select
                  value={sourceId}
                  onChange={(event) => setSourceId(event.target.value)}
                  className="select-shell rounded-[1rem] px-4 py-3 text-sm"
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
                  placeholder="輸入查詢"
                  className="input-shell rounded-[1rem] px-4 py-3 text-sm"
                />
                <button
                  type="button"
                  onClick={handleStartWorkflow}
                  disabled={!selectedInstanceId || !query.trim() || isPending}
                  className="pixel-button rounded-[1rem] bg-coral px-5 py-3 text-sm font-black tracking-[0.05em] text-white disabled:opacity-60"
                >
                  {isPending ? "啟動中..." : "啟動流程"}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                  <label className="space-y-2">
                    <span className="field-label">搜尋內容 / 主題</span>
                    <textarea
                      value={webTopic}
                      onChange={(event) => setWebTopic(event.target.value)}
                      placeholder="輸入主題"
                      rows={3}
                      className="textarea-shell w-full rounded-[1rem] px-4 py-3 text-sm leading-7"
                    />
                  </label>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2">
                      <span className="field-label">回傳格式</span>
                      <select
                        value={webOutputFormat}
                        onChange={(event) => setWebOutputFormat(event.target.value as WebSearchOutputFormat)}
                        className="select-shell w-full rounded-[1rem] px-4 py-3 text-sm"
                      >
                        {WEB_OUTPUT_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2">
                      <span className="field-label">業務分類</span>
                      <select
                        value={businessType}
                        onChange={(event) => setBusinessType((event.target.value || "") as BusinessType | "")}
                        className="select-shell w-full rounded-[1rem] px-4 py-3 text-sm"
                      >
                        <option value="">自動判斷</option>
                        {BUSINESS_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2">
                      <span className="field-label">結果筆數</span>
                      <select
                        value={String(resultLimit)}
                        onChange={(event) => setResultLimit(Number(event.target.value))}
                        className="select-shell w-full rounded-[1rem] px-4 py-3 text-sm"
                      >
                        {[3, 5, 8, 10].map((limit) => (
                          <option key={limit} value={limit}>
                            {limit} 筆
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex items-center gap-3 rounded-[1rem] border border-slate-200 bg-white/80 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={includeProjectSources}
                        onChange={(event) => setIncludeProjectSources(event.target.checked)}
                        className="h-4 w-4"
                      />
                      <span className="text-sm font-black tracking-[0.05em]">合併專案索引結果</span>
                    </label>
                  </div>
                </div>

                <details data-testid="workflow-advanced-filters" className="rounded-[1.25rem] border border-slate-200 bg-white/75 p-4">
                  <summary className="cursor-pointer text-sm font-black tracking-[0.05em] text-ink">進階條件</summary>
                  <div className="mt-4 space-y-4">
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
                        placeholder="每行一個網站"
                      />
                      <WorkflowTextAreaField
                        label="指定搜尋網域"
                        value={targetDomainsText}
                        onChange={setTargetDomainsText}
                        placeholder="每行一個網域"
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
                        placeholder="例如：價格、風險、優缺點"
                      />
                      <label className="space-y-2">
                        <span className="field-label">專案資料源篩選</span>
                        <select
                          value={sourceId}
                          onChange={(event) => setSourceId(event.target.value)}
                          disabled={!includeProjectSources}
                          className="select-shell w-full rounded-[1rem] px-4 py-3 text-sm disabled:bg-slate-100"
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
                </details>

                <button
                  type="button"
                  onClick={handleStartWorkflow}
                  disabled={!selectedInstanceId || !webTopic.trim() || isPending}
                  className="pixel-button rounded-[1rem] bg-coral px-5 py-3 text-sm font-black tracking-[0.05em] text-white disabled:opacity-60"
                >
                  {isPending ? "啟動中..." : "啟動 Web Search + Ingest"}
                </button>
              </div>
            )}

            <div className="status-strip rounded-[1.25rem] px-4 py-4 text-sm leading-6 text-slate-700">
              {error ? <span className="text-coral">{error}</span> : isPending ? "處理中..." : message}
            </div>
          </div>

          <div className="space-y-4">
            <div className="card-muted rounded-[1.5rem] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">整體進度</p>
                  <p className="mt-1 text-2xl font-black text-ink">{activeRun?.overall_progress_percent ?? 0}%</p>
                </div>
                <StatusPill status={activeRun?.status ?? "pending"} />
              </div>
              <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-teal transition-[width]"
                  style={{ width: `${Math.max(0, Math.min(100, activeRun?.overall_progress_percent ?? 0))}%` }}
                />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">
                {activeRun
                  ? `目前進行到 ${activeRun.current_stage ?? "等待啟動"}，處理 agent：${activeRun.active_agent_id ?? "尚未指派"}`
                  : "尚未啟動。"}
              </p>
            </div>

            <RoleSquad roles={workflowRoles} mode="summary" />
          </div>
        </div>
      </section>

      <WorkflowStageBoard run={activeRun} />

      <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <WorkflowRunList runs={runs} activeRunId={activeRun?.id} onSelect={handleSelectRun} />
        <WorkflowEventTimeline events={activeRun?.events ?? []} />
      </div>

      <WorkflowReportPanel
        run={activeRun}
        onExportMarkdown={handleExportMarkdown}
        onContinueToReport={activeRun?.workflow_type === "web_search" && activeRun.status === "completed" ? handleContinueToReport : undefined}
        continueDisabled={isPending}
      />
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
        name: "Ingest Stage",
        tagline: stageAgentMap.get("ingest") ?? "待配置",
        status: stageStatusMap.get("ingest") ?? "pending",
        quote: "我會把高價值搜尋結果合併到既有知識 source，建立可追溯的入庫紀錄。"
      },
      {
        name: "Format Agent",
        tagline: stageAgentMap.get("format") ?? "待配置",
        status: stageStatusMap.get("format") ?? "pending",
        quote: "我會把搜尋結果與入庫摘要整理成摘要、條列、表格或比較格式。"
      },
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
    setBusinessType: (value: BusinessType | "") => void;
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
    setters.setBusinessType(typeof run.input_payload.business_type === "string" ? (run.input_payload.business_type as BusinessType) : "");
    setters.setIncludeProjectSources(Boolean(run.input_payload.include_project_sources));
    setters.setResultLimit(Number(run.input_payload.result_limit ?? 5));
    setters.setSourceId(String(run.input_payload.source_id ?? ""));
    return;
  }

  setters.setQuery(String(run.input_payload.query ?? ""));
  setters.setSourceId(String(run.input_payload.source_id ?? ""));
  setters.setBusinessType("");
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
      className={`rounded-[1rem] border px-4 py-3 text-left transition ${
        active
          ? "border-ink bg-ink text-sand shadow-[0_16px_32px_rgba(17,24,39,0.12)]"
          : "border-slate-200 bg-white/84 text-ink hover:border-slate-300 hover:bg-white"
      }`}
    >
      <p className="text-sm font-black tracking-[0.05em]">{label}</p>
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
      <span className="field-label">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={4}
        className="textarea-shell w-full rounded-[1rem] px-4 py-3 text-sm leading-7"
      />
    </label>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="status-strip rounded-[1.25rem] p-6 text-sm text-slate-600">正在載入工作流頁面...</div>}>
      <SearchWorkflowPageContent />
    </Suspense>
  );
}
