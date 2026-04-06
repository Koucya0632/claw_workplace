import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { WorkflowRunResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

interface WorkflowRunListProps {
  runs: WorkflowRunResponse[];
  activeRunId?: string;
  onSelect: (runId: string) => void;
}

export function WorkflowRunList({ runs, activeRunId, onSelect }: WorkflowRunListProps) {
  // 歷史 run 列表讓使用者可以快速切回之前的處理鏈路，不需要重新送出查詢。
  return (
    <PixelCard title="歷史流程" eyebrow="Runs">
      <div className="space-y-3">
        {runs.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            目前還沒有任何 workflow run。
          </div>
        ) : (
          runs.map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => onSelect(run.id)}
              className={`w-full border-4 border-ink p-4 text-left ${activeRunId === run.id ? "bg-gold/40" : "bg-white"}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-black tracking-[0.08em]">
                    {String(
                      run.input_payload.query ??
                        run.input_payload.topic ??
                        run.input_payload.task_name ??
                        (run.workflow_type === "system_inspection"
                          ? "系統巡檢"
                          : run.workflow_type === "development_execution"
                            ? "工程執行任務"
                            : "未命名查詢")
                    )}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">{run.id}</p>
                </div>
                <StatusPill status={run.status} />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                <span>{workflowTypeLabel(run.workflow_type)}</span>
                <span>{run.current_stage ?? "waiting"}</span>
                <span>{run.overall_progress_percent}%</span>
                <span>{formatDateTime(run.updated_at)}</span>
              </div>
            </button>
          ))
        )}
      </div>
    </PixelCard>
  );
}

function workflowTypeLabel(type: WorkflowRunResponse["workflow_type"]) {
  if (type === "web_search") return "web search";
  if (type === "news_brief") return "news brief";
  if (type === "system_inspection") return "system inspection";
  if (type === "development_execution") return "development";
  return "search report";
}
