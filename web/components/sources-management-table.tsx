import { SourceStatusBadge, SourceSyncBadge } from "@/components/source-badges";
import type { SourceResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

interface SourcesManagementTableProps {
  sources: SourceResponse[];
  busyAction?: string | null;
  onView: (source: SourceResponse) => void;
  onSync: (source: SourceResponse) => Promise<void> | void;
  onEdit: (source: SourceResponse) => void;
  onToggleEnabled: (source: SourceResponse) => Promise<void> | void;
  onDelete: (source: SourceResponse) => Promise<void> | void;
}

export function SourcesManagementTable({
  sources,
  busyAction,
  onView,
  onSync,
  onEdit,
  onToggleEnabled,
  onDelete
}: SourcesManagementTableProps) {
  if (sources.length === 0) {
    return (
      <div className="border-4 border-dashed border-slate-300 bg-white p-8 text-sm text-slate-500">
        目前沒有符合條件的資料源。你可以先新增來源，或調整搜尋 / 篩選條件。
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border-4 border-ink bg-white">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-sand">
          <tr className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="border-b-4 border-ink px-4 py-3">名稱</th>
            <th className="border-b-4 border-ink px-4 py-3">類型</th>
            <th className="border-b-4 border-ink px-4 py-3">狀態</th>
            <th className="border-b-4 border-ink px-4 py-3">同步狀態</th>
            <th className="border-b-4 border-ink px-4 py-3">資料量</th>
            <th className="border-b-4 border-ink px-4 py-3">最後更新</th>
            <th className="border-b-4 border-ink px-4 py-3">最後同步</th>
            <th className="border-b-4 border-ink px-4 py-3">最近同步結果</th>
            <th className="border-b-4 border-ink px-4 py-3">操作</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => {
            const syncKey = `${source.id}:sync`;
            const toggleKey = `${source.id}:toggle`;
            const deleteKey = `${source.id}:delete`;
            return (
              <tr key={source.id} className="align-top even:bg-slate-50">
                <td className="border-b border-slate-200 px-4 py-4">
                  <div className="space-y-1">
                    <p className="font-black tracking-[0.04em] text-ink">{source.name}</p>
                    <p className="max-w-64 truncate text-xs text-slate-500">
                      {source.config.path ?? source.config.url ?? source.config.urls?.[0] ?? "未設定來源"}
                    </p>
                  </div>
                </td>
                <td className="border-b border-slate-200 px-4 py-4 text-slate-700">{source.type}</td>
                <td className="border-b border-slate-200 px-4 py-4">
                  <SourceStatusBadge status={source.is_enabled ? source.status : "disabled"} />
                </td>
                <td className="border-b border-slate-200 px-4 py-4">
                  <SourceSyncBadge status={source.last_sync_status} />
                </td>
                <td className="border-b border-slate-200 px-4 py-4 text-slate-700">{source.document_count}</td>
                <td className="border-b border-slate-200 px-4 py-4 text-xs text-slate-600">
                  {formatDateTime(source.updated_at)}
                </td>
                <td className="border-b border-slate-200 px-4 py-4 text-xs text-slate-600">
                  {formatDateTime(source.last_scan_at)}
                </td>
                <td className="border-b border-slate-200 px-4 py-4 text-xs text-slate-600">
                  <p>成功 {source.last_sync_result.scanned_count}</p>
                  <p>略過 {source.last_sync_result.skipped_count}</p>
                  <p>錯誤 {source.last_sync_result.error_count}</p>
                </td>
                <td className="border-b border-slate-200 px-4 py-4">
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => onView(source)} className="pixel-button bg-slate-100 px-3 py-2 text-xs font-black">
                      查看
                    </button>
                    <button
                      type="button"
                      onClick={() => onSync(source)}
                      disabled={busyAction === syncKey}
                      className="pixel-button bg-teal px-3 py-2 text-xs font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busyAction === syncKey ? "同步中" : "同步"}
                    </button>
                    <button type="button" onClick={() => onEdit(source)} className="pixel-button bg-gold px-3 py-2 text-xs font-black">
                      編輯
                    </button>
                    <button
                      type="button"
                      onClick={() => onToggleEnabled(source)}
                      disabled={busyAction === toggleKey}
                      className="pixel-button bg-slate-100 px-3 py-2 text-xs font-black disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {source.is_enabled ? "停用" : "啟用"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(source)}
                      disabled={busyAction === deleteKey}
                      className="pixel-button bg-coral px-3 py-2 text-xs font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      刪除
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
