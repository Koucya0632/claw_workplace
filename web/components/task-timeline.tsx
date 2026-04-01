import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { RoleStatusEvent } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

interface TaskTimelineProps {
  events: RoleStatusEvent[];
}

export function TaskTimeline({ events }: TaskTimelineProps) {
  // 右側流程欄用事件時間線呈現，讓使用者知道每個角色做了什麼。
  return (
    <PixelCard title="任務流程" eyebrow="Timeline">
      <div className="space-y-4">
        {events.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            任務尚未開始，等待角色啟動。
          </div>
        ) : (
          events.map((event, index) => (
            <div key={event.id} className="relative border-l-4 border-ink pl-4">
              <div className="absolute -left-[11px] top-1 h-4 w-4 border-4 border-ink bg-coral" />
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <p className="text-sm font-black tracking-[0.08em]">{event.role_name}</p>
                <StatusPill status={event.role_status} />
                <span className="text-[11px] text-slate-500">{formatDateTime(event.created_at)}</span>
              </div>
              <p className="text-sm leading-6">{event.message}</p>
              {index !== events.length - 1 ? <div className="mt-4 border-b-2 border-dashed border-slate-200" /> : null}
            </div>
          ))
        )}
      </div>
    </PixelCard>
  );
}

