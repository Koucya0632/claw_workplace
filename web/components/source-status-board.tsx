import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { SourceResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

interface SourceStatusBoardProps {
  sources: SourceResponse[];
  onScan?: (sourceId: string) => void;
  busySourceId?: string | null;
}

export function SourceStatusBoard({ sources, onScan, busySourceId }: SourceStatusBoardProps) {
  // 設定頁與首頁共用資料源狀態卡，方便一致呈現掃描狀態。
  return (
    <PixelCard title="資料源狀態" eyebrow="Sources">
      <div className="space-y-3">
        {sources.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            尚未建立本地資料源，請先在設定頁新增資料夾。
          </div>
        ) : (
          sources.map((source) => (
            <article key={source.id} className="border-4 border-ink bg-white p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-black tracking-[0.08em]">{source.name}</h3>
                  <p className="text-xs text-slate-500">{source.config.path ?? "未設定路徑"}</p>
                </div>
                <StatusPill status={source.status} />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
                <span>最後掃描：{formatDateTime(source.last_scan_at)}</span>
                {onScan ? (
                  <button
                    type="button"
                    onClick={() => onScan(source.id)}
                    disabled={busySourceId === source.id}
                    className="pixel-button bg-teal px-3 py-2 font-black tracking-[0.08em] text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busySourceId === source.id ? "掃描中..." : "重新掃描"}
                  </button>
                ) : null}
              </div>
            </article>
          ))
        )}
      </div>
    </PixelCard>
  );
}

