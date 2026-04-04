import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { WorkflowEvent } from "@/lib/types";
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
            <div key={event.id} className="relative border-l-4 border-ink pl-4">
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
                <pre className="pixel-scrollbar mt-3 max-h-[180px] overflow-auto border-4 border-ink bg-white p-3 text-xs leading-6 whitespace-pre-wrap">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              ) : null}
              {index !== events.length - 1 ? <div className="mt-4 border-b-2 border-dashed border-slate-200" /> : null}
            </div>
          ))
        )}
      </div>
    </PixelCard>
  );
}
