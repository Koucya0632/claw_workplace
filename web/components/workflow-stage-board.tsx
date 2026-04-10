import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { WorkflowRunResponse, WorkflowStageRun } from "@/lib/types";
import { inspectWorkflowPayload, summarizeWorkflowRuntimeIssue } from "@/lib/workflow-payloads";
import { cn, formatDateTime } from "@/lib/utils";

const STAGE_LABELS: Record<string, string> = {
  understand: "理解",
  monitor: "監控",
  snapshot: "快照",
  version_check: "版本",
  log_review: "日誌",
  risk_assessment: "風險",
  problem_definition: "問題定義",
  requirements_analysis: "需求",
  solution_design: "設計",
  technology_selection: "選型",
  task_planning: "排期",
  implementation: "開發",
  testing: "測試",
  optimization: "優化",
  handoff: "匯報",
  search: "搜索",
  dedupe: "去重",
  filter: "過濾",
  ingest: "入庫",
  rank: "排序",
  analysis: "分析",
  format: "輸出",
  brief: "簡報",
  report: "報告"
};

interface WorkflowStageBoardProps {
  run?: WorkflowRunResponse | null;
  compact?: boolean;
}

export function WorkflowStageBoard({ run, compact = true }: WorkflowStageBoardProps) {
  const stages = run?.stages ?? [];

  return (
    <PixelCard title="流程階段" eyebrow="Pipeline">
      <div className="grid gap-4 xl:grid-cols-3">
        {!run || stages.length === 0 ? (
          <div className="rounded-[1.25rem] border border-dashed border-slate-300 p-4 text-sm text-slate-500 xl:col-span-3">
            尚未建立 workflow run。送出後會在這裡顯示各階段進度。
          </div>
        ) : (
          stages.map((stage, index) => (
            <WorkflowStageCard
              key={stage.id}
              run={run}
              stage={stage}
              stepNumber={index + 1}
              totalSteps={stages.length}
              compact={compact}
            />
          ))
        )}
      </div>
    </PixelCard>
  );
}

interface WorkflowStageCardProps {
  run: WorkflowRunResponse;
  stage: WorkflowStageRun;
  stepNumber: number;
  totalSteps: number;
  compact: boolean;
}

function WorkflowStageCard({ run, stage, stepNumber, totalSteps, compact }: WorkflowStageCardProps) {
  const isActive = run.active_agent_id === stage.agent_id && run.current_stage === stage.stage_key && run.status === "running";
  const recentEvent = [...run.events].reverse().find((event) => event.stage_key === stage.stage_key);
  const outputPayload = stage.output_payload ?? (stage.status === "failed" ? recentEvent?.payload : undefined);
  const detailPayload = outputPayload ?? stage.input_payload;
  const runtimePayload = inspectWorkflowPayload(detailPayload);
  const runtimeSummary = summarizeWorkflowRuntimeIssue(detailPayload);
  const hasPayloadDetails = Boolean(
    (stage.input_payload && Object.keys(stage.input_payload).length > 0) ||
      (outputPayload && Object.keys(outputPayload).length > 0)
  );

  return (
    <article
      className={cn(
        "rounded-[1.35rem] border border-slate-200 bg-white/92 p-4 transition",
        isActive && "border-gold/50 bg-gold/18 shadow-[0_16px_36px_rgba(240,180,41,0.18)]",
        stage.status === "completed" && "border-mint/50 bg-mint/30",
        stage.status === "failed" && "border-coral/50 bg-coral/12"
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-black tracking-[0.16em] text-slate-500">
            STEP {stepNumber} / {totalSteps}
          </p>
          <h3 className="mt-1 text-base font-black tracking-[0.08em]">{STAGE_LABELS[stage.stage_key] ?? stage.stage_key}</h3>
        </div>
        <StatusPill status={stage.status} />
      </div>

      <div className="space-y-3 text-sm">
        <div className="rounded-[1rem] border border-slate-200 bg-sand/60 p-3">
          <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">負責 AGENT</p>
          <p className="mt-2 break-all font-black">{stage.agent_id}</p>
        </div>

        <div className="rounded-[1rem] border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">完成進度</p>
            <span className="text-xs font-black">{stage.progress_percent}%</span>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200">
            <div
              className={cn(
                "h-full rounded-full bg-teal transition-[width]",
                stage.status === "running" && "bg-gold",
                stage.status === "failed" && "bg-coral"
              )}
              style={{ width: `${Math.max(0, Math.min(100, stage.progress_percent))}%` }}
            />
          </div>
        </div>

        <div className="rounded-[1rem] border border-slate-200 bg-white p-3">
          <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">最近狀態</p>
          <p className="mt-2 leading-6">{recentEvent?.message ?? "等待執行。"}</p>
        </div>

        {compact ? (
          hasPayloadDetails ? (
            <details className="rounded-[1rem] border border-slate-200 bg-white p-3">
              <summary className="cursor-pointer text-[11px] font-black tracking-[0.12em] text-slate-500">
                查看詳情
              </summary>
              <div className="mt-3 space-y-3">
                {runtimeSummary ? (
                  <div className="rounded-[0.95rem] border border-slate-200 bg-sand/70 p-3 text-xs leading-6 text-slate-700">
                    <p className="font-black text-slate-800">{runtimeSummary}</p>
                    {runtimePayload?.highlights && runtimePayload.highlights.length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {runtimePayload.highlights.slice(0, 3).map((item) => (
                          <li key={item}>- {item}</li>
                        ))}
                      </ul>
                    ) : null}
                    {runtimePayload?.artifacts && runtimePayload.artifacts.length > 0 ? (
                      <p className="mt-2 text-slate-600">關聯模組：{runtimePayload.artifacts.slice(0, 4).join("、")}</p>
                    ) : null}
                  </div>
                ) : null}
                <div className="grid gap-3">
                  <WorkflowPayloadCard label="輸入資料" payload={stage.input_payload} compact />
                  <WorkflowPayloadCard label="輸出結果" payload={outputPayload ?? undefined} compact />
                </div>
              </div>
            </details>
          ) : null
        ) : (
          <div className="grid gap-3">
            <WorkflowPayloadCard label="輸入資料" payload={stage.input_payload} />
            <WorkflowPayloadCard label="輸出結果" payload={outputPayload ?? undefined} />
          </div>
        )}

        <div className="text-[11px] text-slate-500">
          開始：{formatDateTime(stage.started_at)} / 完成：{formatDateTime(stage.completed_at)}
        </div>
      </div>
    </article>
  );
}

interface WorkflowPayloadCardProps {
  label: string;
  payload?: Record<string, unknown>;
  compact?: boolean;
}

function WorkflowPayloadCard({ label, payload, compact = false }: WorkflowPayloadCardProps) {
  const runtimePayload = inspectWorkflowPayload(payload);
  const runtimeSummary = summarizeWorkflowRuntimeIssue(payload);

  return (
    <div className="rounded-[1rem] border border-slate-200 bg-white p-3">
      <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">{label}</p>
      {payload && Object.keys(payload).length > 0 ? (
        runtimePayload ? (
          <div className="mt-2 space-y-3 text-xs leading-6">
            <div className="rounded-[0.9rem] border border-slate-200 bg-sand/70 p-3">
              <p className="font-black text-slate-800">{runtimeSummary}</p>
              {runtimePayload.highlights && runtimePayload.highlights.length > 0 ? (
                <ul className="mt-2 space-y-1 text-slate-700">
                  {runtimePayload.highlights.slice(0, 3).map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-slate-600">
                {runtimePayload.status ? <span>狀態：{runtimePayload.status}</span> : null}
                {runtimePayload.summary ? <span>摘要：{runtimePayload.summary}</span> : null}
                {runtimePayload.provider ? <span>Provider：{runtimePayload.provider}</span> : null}
                {runtimePayload.model ? <span>Model：{runtimePayload.model}</span> : null}
                {typeof runtimePayload.durationMs === "number" ? (
                  <span>耗時：約 {(runtimePayload.durationMs / 1000).toFixed(1)} 秒</span>
                ) : null}
              </div>
              {runtimePayload.artifacts && runtimePayload.artifacts.length > 0 ? (
                <p className="mt-2 text-slate-600">關聯模組：{runtimePayload.artifacts.slice(0, 4).join("、")}</p>
              ) : null}
            </div>
            {!compact ? (
              <details className="rounded-[0.9rem] border border-slate-200 bg-white p-3">
                <summary className="cursor-pointer font-black tracking-[0.08em] text-slate-600">查看原始 payload</summary>
                <pre className="pixel-scrollbar mt-2 max-h-[180px] overflow-auto whitespace-pre-wrap">
                  {JSON.stringify(payload, null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        ) : (
          compact ? (
            <p className="mt-2 text-xs text-slate-500">已附資料，可展開原始 payload。</p>
          ) : (
            <pre className="pixel-scrollbar mt-2 max-h-[180px] overflow-auto text-xs leading-6 whitespace-pre-wrap">
              {JSON.stringify(payload, null, 2)}
            </pre>
          )
        )
      ) : (
        <p className="mt-2 text-xs text-slate-500">目前尚無資料。</p>
      )}
    </div>
  );
}
