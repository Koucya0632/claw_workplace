import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { WorkflowRunResponse, WorkflowStageRun } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

const STAGE_LABELS: Record<string, string> = {
  understand: "理解",
  search: "搜索",
  filter: "過濾",
  analysis: "分析",
  format: "輸出",
  report: "報告"
};

interface WorkflowStageBoardProps {
  run?: WorkflowRunResponse | null;
}

export function WorkflowStageBoard({ run }: WorkflowStageBoardProps) {
  // 三階段流程板是整個一體化工作台的主視覺，因此直接把 agent、進度、輸入與輸出集中展示。
  const stages = run?.stages ?? [];

  return (
    <PixelCard title="流程階段" eyebrow="Pipeline">
      <div className="grid gap-4 xl:grid-cols-3">
        {!run || stages.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500 xl:col-span-3">
            尚未建立 workflow run。送出查詢後，這裡會依序顯示目前流程的每個階段與 agent 狀態。
          </div>
        ) : (
          stages.map((stage, index) => (
            <WorkflowStageCard key={stage.id} run={run} stage={stage} stepNumber={index + 1} totalSteps={stages.length} />
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
}

function WorkflowStageCard({ run, stage, stepNumber, totalSteps }: WorkflowStageCardProps) {
  // active agent 會用高亮框與背景區隔，讓使用者一眼知道目前處理到哪個 stage。
  const isActive = run.active_agent_id === stage.agent_id && run.current_stage === stage.stage_key && run.status === "running";
  const recentEvent = [...run.events].reverse().find((event) => event.stage_key === stage.stage_key);

  return (
    <article
      className={cn(
        "border-4 border-ink bg-white p-4 transition",
        isActive && "bg-gold/40 shadow-[8px_8px_0_0_rgba(15,23,42,0.2)]",
        stage.status === "completed" && "bg-mint/50",
        stage.status === "failed" && "bg-coral/85 text-white"
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
        <div className="border-4 border-ink bg-sand p-3">
          <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">負責 AGENT</p>
          <p className="mt-2 break-all font-black">{stage.agent_id}</p>
        </div>

        <div className="border-4 border-ink bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">完成進度</p>
            <span className="text-xs font-black">{stage.progress_percent}%</span>
          </div>
          <div className="mt-3 h-4 border-2 border-ink bg-slate-100">
            <div
              className={cn(
                "h-full bg-teal transition-[width]",
                stage.status === "running" && "bg-gold",
                stage.status === "failed" && "bg-coral"
              )}
              style={{ width: `${Math.max(0, Math.min(100, stage.progress_percent))}%` }}
            />
          </div>
        </div>

        <div className="border-4 border-ink bg-white p-3">
          <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">最近狀態</p>
          <p className="mt-2 leading-6">{recentEvent?.message ?? "等待執行。"}</p>
        </div>

        <div className="grid gap-3">
          <WorkflowPayloadCard label="輸入資料" payload={stage.input_payload} />
          <WorkflowPayloadCard label="輸出結果" payload={stage.output_payload ?? undefined} />
        </div>

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
}

function WorkflowPayloadCard({ label, payload }: WorkflowPayloadCardProps) {
  // 輸入與輸出都保留 JSON 摘要，方便回看中間成果而不需要另外切頁。
  return (
    <div className="border-4 border-ink bg-white p-3">
      <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">{label}</p>
      {payload && Object.keys(payload).length > 0 ? (
        <pre className="pixel-scrollbar mt-2 max-h-[180px] overflow-auto text-xs leading-6 whitespace-pre-wrap">
          {JSON.stringify(payload, null, 2)}
        </pre>
      ) : (
        <p className="mt-2 text-xs text-slate-500">目前尚無資料。</p>
      )}
    </div>
  );
}
