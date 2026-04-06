"use client";

import { PixelCard } from "@/components/pixel-card";
import { SourceStatusBadge, SourceSyncBadge } from "@/components/source-badges";
import type { SourceDetailResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

interface SourceDetailDrawerProps {
  source: SourceDetailResponse | null;
  open: boolean;
  busyAction?: string | null;
  onClose: () => void;
  onSync: (sourceId: string) => Promise<void> | void;
  onEdit: (source: SourceDetailResponse) => void;
  onToggleEnabled: (source: SourceDetailResponse) => Promise<void> | void;
  onDelete: (source: SourceDetailResponse) => Promise<void> | void;
}

function renderConfigSummary(source: SourceDetailResponse) {
  if (source.type === "local") {
    return source.config.path ?? "未設定路徑";
  }
  if (source.type === "url_list") {
    return `${source.config.urls?.length ?? 0} 個 URL`;
  }
  return source.config.url ?? source.config.workspace_name ?? "尚未配置";
}

export function SourceDetailDrawer({
  source,
  open,
  busyAction,
  onClose,
  onSync,
  onEdit,
  onToggleEnabled,
  onDelete
}: SourceDetailDrawerProps) {
  if (!open || !source) {
    return null;
  }

  const isBusy = (action: string) => busyAction === `${source.id}:${action}`;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-2xl border-l-4 border-ink bg-paper p-4 shadow-[-12px_0_0_0_#111827]">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Source Detail</p>
          <h3 className="mt-2 text-2xl font-black tracking-[0.06em] text-ink">{source.name}</h3>
          <p className="mt-2 text-sm text-slate-600">{renderConfigSummary(source)}</p>
        </div>
        <button type="button" onClick={onClose} className="pixel-button bg-slate-100 px-3 py-2 text-xs font-black">
          關閉
        </button>
      </div>

      <div className="grid gap-4 overflow-y-auto pb-8">
        <PixelCard title="基本資訊" eyebrow="Overview">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-3 text-sm text-slate-700">
              <p><span className="font-black">類型：</span>{source.type}</p>
              <p><span className="font-black">建立時間：</span>{formatDateTime(source.created_at)}</p>
              <p><span className="font-black">最後更新：</span>{formatDateTime(source.updated_at)}</p>
              <p><span className="font-black">最後同步：</span>{formatDateTime(source.last_scan_at)}</p>
            </div>
            <div className="space-y-3 text-sm text-slate-700">
              <div className="flex flex-wrap gap-2">
                <SourceStatusBadge status={source.is_enabled ? source.status : "disabled"} />
                <SourceSyncBadge status={source.last_sync_status} />
              </div>
              <p><span className="font-black">資料量：</span>{source.document_count} 份</p>
              <p><span className="font-black">版本數：</span>{source.version_count}</p>
              <p><span className="font-black">最近成功：</span>{formatDateTime(source.last_successful_sync_at)}</p>
            </div>
          </div>
        </PixelCard>

        <PixelCard title="來源設定" eyebrow="Config">
          <div className="grid gap-3 text-sm text-slate-700">
            {source.config.path ? <p><span className="font-black">Path：</span>{source.config.path}</p> : null}
            {source.config.url ? <p><span className="font-black">URL：</span>{source.config.url}</p> : null}
            {source.config.urls?.length ? (
              <div>
                <p className="font-black">URLs：</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {source.config.urls.map((value) => (
                    <li key={value} className="break-all">{value}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {Object.keys(source.config.extra ?? {}).length > 0 ? (
              <pre className="overflow-x-auto border-4 border-ink bg-white p-3 text-xs text-slate-700">
                {JSON.stringify(source.config.extra, null, 2)}
              </pre>
            ) : (
              <p className="text-slate-500">沒有額外設定。</p>
            )}
          </div>
        </PixelCard>

        <PixelCard title="最近同步" eyebrow="Activity">
          <div className="space-y-3">
            {source.recent_activity.length === 0 ? (
              <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">尚無同步紀錄。</div>
            ) : (
              source.recent_activity.map((event) => (
                <article key={event.id} className="border-4 border-ink bg-white p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <SourceSyncBadge status={event.status} />
                    <span className="text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{event.message}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    成功 {event.scanned_count} / 略過 {event.skipped_count} / 錯誤 {event.error_count}
                  </p>
                </article>
              ))
            )}
          </div>
        </PixelCard>

        <PixelCard title="快速操作" eyebrow="Actions">
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => onSync(source.id)}
              disabled={isBusy("sync")}
              className="pixel-button bg-teal px-4 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isBusy("sync") ? "同步中..." : "立即同步"}
            </button>
            <button type="button" onClick={() => onEdit(source)} className="pixel-button bg-gold px-4 py-3 text-sm font-black">
              編輯
            </button>
            <button
              type="button"
              onClick={() => onToggleEnabled(source)}
              disabled={isBusy("toggle")}
              className="pixel-button bg-slate-100 px-4 py-3 text-sm font-black"
            >
              {source.is_enabled ? "停用" : "啟用"}
            </button>
            <button
              type="button"
              onClick={() => onDelete(source)}
              disabled={isBusy("delete")}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              刪除
            </button>
          </div>
          {source.last_sync_error ? (
            <div className="mt-4 border-4 border-coral bg-coral/10 p-4 text-sm text-coral">
              最近錯誤：{source.last_sync_error}
            </div>
          ) : null}
        </PixelCard>
      </div>
    </div>
  );
}
