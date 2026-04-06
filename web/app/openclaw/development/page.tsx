"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { WorkflowEventTimeline } from "@/components/workflow-event-timeline";
import { WorkflowReportPanel } from "@/components/workflow-report-panel";
import { WorkflowRunList } from "@/components/workflow-run-list";
import { WorkflowStageBoard } from "@/components/workflow-stage-board";
import {
  createDevelopmentExecutionWorkflow,
  fetchOpenClawInstances,
  fetchWorkflowRun,
  fetchWorkflowRuns
} from "@/lib/api";
import type { OpenClawInstanceResponse, WorkflowDevelopmentExecutionCreateRequest, WorkflowRunResponse } from "@/lib/types";

const DEVELOPMENT_ROLES = [
  {
    name: "Main Agent",
    tagline: "任務 Intake / 最終接收",
    status: "running",
    quote: "我會接需求、建立工程 workflow，並在 handoff 階段接收全端工程師的結構化報告。"
  },
  {
    name: "Fullstack Engineer",
    tagline: "唯一執行入口",
    status: "ready",
    quote: "我會依序完成問題定義、需求分析、方案設計、技術選型、排期、開發、測試與優化。"
  },
  {
    name: "Traceable Workflow",
    tagline: "可追蹤 / 可回看",
    status: "ready",
    quote: "所有工程階段都會保留 stage board、timeline 與最終報告，方便回看與後續迭代。"
  }
];

const DEFAULT_FORM: WorkflowDevelopmentExecutionCreateRequest = {
  instance_id: "",
  task_name: "",
  problem_background: "",
  goal: "",
  constraints: [],
  success_criteria: [],
  context: "",
  attachments: [],
  references: []
};

function parseLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function OpenClawDevelopmentPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [form, setForm] = useState(DEFAULT_FORM);
  const [constraintsText, setConstraintsText] = useState("");
  const [successCriteriaText, setSuccessCriteriaText] = useState("");
  const [attachmentsText, setAttachmentsText] = useState("");
  const [referencesText, setReferencesText] = useState("");
  const [runs, setRuns] = useState<WorkflowRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("這裡會把工程任務交給 fullstack-engineer-agent，並強制保留分析、設計、測試與匯報鏈路。");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        const nextInstanceId = instancePayload[0]?.id ?? "";
        setSelectedInstanceId((current) => current || nextInstanceId);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Instances");
      }
    });
  }, [startTransition]);

  useEffect(() => {
    setForm((current) => ({ ...current, instance_id: selectedInstanceId }));
    if (!selectedInstanceId) return;
    startTransition(async () => {
      try {
        const runPayload = await fetchWorkflowRuns({
          instanceId: selectedInstanceId,
          workflowType: "development_execution",
          limit: 8
        });
        setRuns(runPayload);
        setActiveRun(runPayload[0] ?? null);
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 Development workflow");
      }
    });
  }, [selectedInstanceId, startTransition]);

  useEffect(() => {
    if (!activeRun || !["pending", "running"].includes(activeRun.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const nextRun = await fetchWorkflowRun(activeRun.id);
        setActiveRun(nextRun);
        setRuns(
          await fetchWorkflowRuns({
            instanceId: selectedInstanceId,
            workflowType: "development_execution",
            limit: 8
          })
        );
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "輪詢工程 workflow 失敗");
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [activeRun, selectedInstanceId]);

  async function handleCreateRun() {
    if (!selectedInstanceId || !form.task_name.trim() || !form.problem_background.trim() || !form.goal.trim()) {
      setError("請至少填寫 Instance、任務名稱、問題背景與目標。");
      return;
    }
    setError("");
    setMessage("正在交由 fullstack-engineer-agent 建立標準化工程執行流程...");
    startTransition(async () => {
      try {
        const payload: WorkflowDevelopmentExecutionCreateRequest = {
          instance_id: selectedInstanceId,
          task_name: form.task_name.trim(),
          problem_background: form.problem_background.trim(),
          goal: form.goal.trim(),
          constraints: parseLines(constraintsText),
          success_criteria: parseLines(successCriteriaText),
          context: form.context.trim(),
          attachments: parseLines(attachmentsText),
          references: parseLines(referencesText)
        };
        const run = await createDevelopmentExecutionWorkflow(payload);
        setActiveRun(run);
        setRuns(
          await fetchWorkflowRuns({
            instanceId: selectedInstanceId,
            workflowType: "development_execution",
            limit: 8
          })
        );
        setMessage("工程任務已建立，現在會依序執行問題定義、設計、排期、開發、測試與匯報。");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 Development workflow 失敗");
      }
    });
  }

  return (
    <OpenClawPageShell
      title="Development"
      description="把工程任務交給 fullstack-engineer-agent，強制保留問題定義、需求分析、方案設計、技術選型、排期、開發、測試、優化與最終 handoff。"
      roles={DEVELOPMENT_ROLES}
    >
      <PixelCard title="工程任務建立" eyebrow="Development Workflow">
        <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm leading-7 text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message}
          </div>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">任務名稱</span>
            <input
              value={form.task_name}
              onChange={(event) => setForm((current) => ({ ...current, task_name: event.target.value }))}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">目標</span>
            <input
              value={form.goal}
              onChange={(event) => setForm((current) => ({ ...current, goal: event.target.value }))}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">問題背景</span>
            <textarea
              value={form.problem_background}
              onChange={(event) => setForm((current) => ({ ...current, problem_background: event.target.value }))}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">上下文 / 補充說明</span>
            <textarea
              value={form.context}
              onChange={(event) => setForm((current) => ({ ...current, context: event.target.value }))}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">限制條件（每行一條）</span>
            <textarea
              value={constraintsText}
              onChange={(event) => setConstraintsText(event.target.value)}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">成功標準（每行一條）</span>
            <textarea
              value={successCriteriaText}
              onChange={(event) => setSuccessCriteriaText(event.target.value)}
              rows={5}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">附件（每行一條）</span>
            <textarea
              value={attachmentsText}
              onChange={(event) => setAttachmentsText(event.target.value)}
              rows={4}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">參考資料（每行一條）</span>
            <textarea
              value={referencesText}
              onChange={(event) => setReferencesText(event.target.value)}
              rows={4}
              className="pixel-scrollbar w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none"
            />
          </label>
        </div>

        <button
          type="button"
          onClick={handleCreateRun}
          disabled={isPending || !selectedInstanceId}
          className="pixel-button mt-4 bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
        >
          {isPending ? "建立中..." : "建立工程任務"}
        </button>
      </PixelCard>

      <WorkflowStageBoard run={activeRun} />

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <WorkflowRunList runs={runs} activeRunId={activeRun?.id} onSelect={async (runId) => setActiveRun(await fetchWorkflowRun(runId))} />
        <WorkflowEventTimeline events={activeRun?.events ?? []} />
      </div>

      <WorkflowReportPanel run={activeRun} />
    </OpenClawPageShell>
  );
}
