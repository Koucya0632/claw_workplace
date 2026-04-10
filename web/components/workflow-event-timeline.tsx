import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { WorkflowEvent } from "@/lib/types";
import { inspectWorkflowPayload, summarizeWorkflowRuntimeIssue } from "@/lib/workflow-payloads";
import { formatDateTime } from "@/lib/utils";

interface WorkflowEventTimelineProps {
  events: WorkflowEvent[];
}

export function WorkflowEventTimeline({ events }: WorkflowEventTimelineProps) {
  // workflow timeline 直接展示每條進度訊息，讓使用者知道 agent 在什麼時間做了什麼事。
  return (
    <PixelCard title="處理鏈路" eyebrow="Timeline">
      <div className="space-y-4">
        {events.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            任務尚未開始，等待第一條 workflow 事件。
          </div>
        ) : (
          events.map((event, index) => (
            <WorkflowEventItem key={event.id} event={event} isLast={index === events.length - 1} />
          ))
        )}
      </div>
    </PixelCard>
  );
}

function WorkflowEventItem({ event, isLast }: { event: WorkflowEvent; isLast: boolean }) {
  const runtimePayload = inspectWorkflowPayload(event.payload);
  const runtimeSummary = summarizeWorkflowRuntimeIssue(event.payload);

  return (
    <div className="relative border-l-4 border-ink pl-4">
      <div className="absolute -left-[11px] top-1 h-4 w-4 border-4 border-ink bg-coral" />
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className="text-sm font-black tracking-[0.08em]">{event.stage_key ?? "workflow"}</p>
        {event.agent_id ? <span className="text-xs text-slate-500">{event.agent_id}</span> : null}
        <StatusPill status={event.status} />
        <span className="text-[11px] text-slate-500">{event.progress_percent}%</span>
        <span className="text-[11px] text-slate-500">{formatDateTime(event.created_at)}</span>
      </div>
      <p className="text-sm leading-6">{event.message}</p>
      {Object.keys(event.payload).length > 0 ? (
        runtimePayload ? (
          <div className="mt-3 space-y-3 border-4 border-ink bg-white p-3 text-xs leading-6">
            <p className="font-black text-slate-800">{runtimeSummary}</p>
            {runtimePayload.highlights && runtimePayload.highlights.length > 0 ? (
              <ul className="space-y-1 text-slate-700">
                {runtimePayload.highlights.slice(0, 3).map((item) => (
                  <li key={item}>- {item}</li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-slate-600">
              {runtimePayload.status ? <span>狀態：{runtimePayload.status}</span> : null}
              {runtimePayload.summary ? <span>摘要：{runtimePayload.summary}</span> : null}
              {runtimePayload.provider ? <span>Provider：{runtimePayload.provider}</span> : null}
              {runtimePayload.model ? <span>Model：{runtimePayload.model}</span> : null}
              {typeof runtimePayload.durationMs === "number" ? (
                <span>耗時：約 {(runtimePayload.durationMs / 1000).toFixed(1)} 秒</span>
              ) : null}
            </div>
            {runtimePayload.artifacts && runtimePayload.artifacts.length > 0 ? (
              <p className="text-slate-600">關聯模組：{runtimePayload.artifacts.slice(0, 4).join("、")}</p>
            ) : null}
            <details>
              <summary className="cursor-pointer font-black tracking-[0.08em] text-slate-600">查看原始 payload</summary>
              <pre className="pixel-scrollbar mt-2 max-h-[180px] overflow-auto whitespace-pre-wrap">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <pre className="pixel-scrollbar mt-3 max-h-[180px] overflow-auto border-4 border-ink bg-white p-3 text-xs leading-6 whitespace-pre-wrap">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        )
      ) : null}
      {!isLast ? <div className="mt-4 border-b-2 border-dashed border-slate-200" /> : null}
    </div>
  );
}
