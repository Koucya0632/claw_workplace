"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import { PixelCard } from "@/components/pixel-card";
import { SourceDetailDrawer } from "@/components/source-detail-drawer";
import { SourceFormDialog } from "@/components/source-form-dialog";
import { SourceMetricsGrid } from "@/components/source-metrics-grid";
import { SourcesManagementTable } from "@/components/sources-management-table";
import {
  createSource,
  deleteSource,
  disableSource,
  enableSource,
  fetchSourceDetail,
  fetchSourceMetrics,
  fetchSources,
  scanSource,
  updateSource
} from "@/lib/api";
import type { SourceDetailResponse, SourceMetricsResponse, SourceResponse, SourceType } from "@/lib/types";

const DEFAULT_METRICS: SourceMetricsResponse = {
  total_sources: 0,
  healthy_sources: 0,
  warning_sources: 0,
  failed_sources: 0,
  syncing_sources: 0,
  disabled_sources: 0,
  recently_updated_sources: 0,
  recent_sync_failures: 0
};

const SOURCE_TYPE_OPTIONS: Array<{ value: "" | SourceType; label: string }> = [
  { value: "", label: "全部類型" },
  { value: "local", label: "Local" },
  { value: "web_page", label: "Web Page" },
  { value: "url_list", label: "URL List" },
  { value: "rss_feed", label: "RSS Feed" },
  { value: "notion", label: "Notion" },
  { value: "google_drive", label: "Google Drive" }
];

const STATUS_OPTIONS = [
  { value: "", label: "全部狀態" },
  { value: "healthy", label: "正常" },
  { value: "warning", label: "異常" },
  { value: "syncing", label: "同步中" },
  { value: "disabled", label: "停用" },
  { value: "never_scanned", label: "未同步" }
];

const SORT_OPTIONS = [
  { value: "updated_at", label: "最後更新" },
  { value: "last_sync", label: "最後同步" },
  { value: "name", label: "名稱" },
  { value: "document_count", label: "資料量" },
  { value: "status", label: "狀態" }
] as const;

export default function SourceSettingsPage() {
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [metrics, setMetrics] = useState<SourceMetricsResponse>(DEFAULT_METRICS);
  const [selectedSource, setSelectedSource] = useState<SourceDetailResponse | null>(null);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | SourceType>("");
  const [sortKey, setSortKey] = useState<(typeof SORT_OPTIONS)[number]["value"]>("updated_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<SourceResponse | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  const visibleSources = useMemo(() => sources, [sources]);

  async function loadSources() {
    const [sourcePayload, metricsPayload] = await Promise.all([
      fetchSources({
        q: query || undefined,
        status: statusFilter || undefined,
        type: typeFilter || undefined,
        sort: sortKey,
        order: sortOrder
      }),
      fetchSourceMetrics()
    ]);
    setSources(sourcePayload);
    setMetrics(metricsPayload);
  }

  async function reloadSelectedSource(sourceId: string) {
    const detail = await fetchSourceDetail(sourceId);
    setSelectedSource(detail);
  }

  useEffect(() => {
    startTransition(async () => {
      try {
        await loadSources();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入資料源");
      }
    });
  }, [query, statusFilter, typeFilter, sortKey, sortOrder]);

  async function refreshAfterMutation(nextMessage: string, selectedId?: string | null) {
    await loadSources();
    if (selectedId) {
      await reloadSelectedSource(selectedId);
    }
    setMessage(nextMessage);
  }

  async function handleCreateOrUpdate(payload: {
    name: string;
    type: SourceType;
    config: {
      path?: string | null;
      url?: string | null;
      urls?: string[];
      root_page_id?: string | null;
      database_id?: string | null;
      workspace_name?: string | null;
      extra?: Record<string, unknown>;
    };
  }) {
    setError("");
    setMessage("");

    if (editingSource) {
      await updateSource(editingSource.id, {
        name: payload.name,
        config: payload.config
      });
      await refreshAfterMutation(`已更新資料源：${payload.name}`, editingSource.id);
    } else {
      const created = await createSource({
        name: payload.name,
        type: payload.type,
        config: payload.config
      });
      await refreshAfterMutation(`已建立資料源：${created.name}`, created.id);
      setSelectedSource(await fetchSourceDetail(created.id));
    }

    setDialogOpen(false);
    setEditingSource(null);
  }

  async function handleScan(source: SourceResponse) {
    setBusyAction(`${source.id}:sync`);
    setError("");
    setMessage("");
    try {
      const result = await scanSource(source.id);
      await refreshAfterMutation(
        `同步完成：${source.name} 成功 ${result.scanned_count}，略過 ${result.skipped_count}`,
        selectedSource?.id === source.id ? source.id : null
      );
      if (result.errors.length > 0) {
        setError(result.errors.join("；"));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "同步失敗");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleToggleEnabled(source: SourceResponse) {
    setBusyAction(`${source.id}:toggle`);
    setError("");
    setMessage("");
    try {
      if (source.is_enabled) {
        await disableSource(source.id);
        await refreshAfterMutation(`已停用資料源：${source.name}`, selectedSource?.id === source.id ? source.id : null);
      } else {
        await enableSource(source.id);
        await refreshAfterMutation(`已啟用資料源：${source.name}`, selectedSource?.id === source.id ? source.id : null);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "切換狀態失敗");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDelete(source: SourceResponse) {
    if (!window.confirm(`確定要刪除資料源「${source.name}」嗎？此操作會連同索引文件一起刪除。`)) {
      return;
    }

    setBusyAction(`${source.id}:delete`);
    setError("");
    setMessage("");
    try {
      await deleteSource(source.id);
      setSelectedSource((current) => (current?.id === source.id ? null : current));
      await loadSources();
      setMessage(`已刪除資料源：${source.name}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "刪除資料源失敗");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleView(source: SourceResponse) {
    setBusyAction(`${source.id}:view`);
    setError("");
    try {
      setSelectedSource(await fetchSourceDetail(source.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "無法載入來源詳情");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleBatchRefresh() {
    setError("");
    setMessage("");
    setBusyAction("batch");
    const refreshTargets = visibleSources.filter((source) => source.is_enabled);
    try {
      const results = await Promise.allSettled(refreshTargets.map((source) => scanSource(source.id)));
      const failedCount = results.filter((item) => item.status === "rejected").length;
      await loadSources();
      setMessage(`批次同步完成：${refreshTargets.length - failedCount} 成功，${failedCount} 失敗。`);
      if (selectedSource) {
        await reloadSelectedSource(selectedSource.id);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "批次同步失敗");
    } finally {
      setBusyAction(null);
    }
  }

  function openCreateDialog() {
    setEditingSource(null);
    setDialogOpen(true);
  }

  function openEditDialog(source: SourceResponse) {
    setEditingSource(source);
    setDialogOpen(true);
  }

  return (
    <div className="space-y-5">
      <SourceMetricsGrid metrics={metrics} />

      <PixelCard title="資料源管理台" eyebrow="Sources Console">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto_auto_auto]">
          <label className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">搜尋</span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  setQuery(searchInput.trim());
                }
              }}
              placeholder="搜尋名稱、類型、路徑、URL"
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
          </label>

          <label className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">狀態</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">類型</span>
            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as "" | SourceType)}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            >
              {SOURCE_TYPE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">排序</span>
            <select
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as (typeof SORT_OPTIONS)[number]["value"])}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-[10px] uppercase tracking-[0.24em] text-slate-500">排序方向</span>
            <select
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value as "asc" | "desc")}
              className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            >
              <option value="desc">由新到舊</option>
              <option value="asc">由舊到新</option>
            </select>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setQuery(searchInput.trim())}
            className="pixel-button bg-slate-100 px-4 py-3 text-sm font-black"
          >
            搜尋
          </button>
          <button
            type="button"
            onClick={() => {
              setStatusFilter("warning");
              setSortKey("last_sync");
              setSortOrder("desc");
            }}
            className="pixel-button bg-gold px-4 py-3 text-sm font-black"
          >
            只看異常
          </button>
          <button
            type="button"
            onClick={handleBatchRefresh}
            disabled={busyAction === "batch" || visibleSources.length === 0}
            className="pixel-button bg-teal px-4 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "batch" ? "批次同步中..." : "批次重新整理"}
          </button>
          <button
            type="button"
            onClick={openCreateDialog}
            className="pixel-button bg-coral px-4 py-3 text-sm font-black text-white"
          >
            新增資料源
          </button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="border-4 border-ink bg-white p-4 text-sm text-slate-700">
            <p>頁面會直接顯示文件數、最近同步狀態與錯誤摘要，方便優先處理異常來源。</p>
          </div>
          <div className="border-4 border-ink bg-sand p-4 text-sm text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message || (isPending ? "正在同步資料源狀態..." : "資料源管理台已就緒。")}
          </div>
        </div>
      </PixelCard>

      <PixelCard title="資料源總表" eyebrow="Management Table">
        <SourcesManagementTable
          sources={visibleSources}
          busyAction={busyAction}
          onView={handleView}
          onSync={handleScan}
          onEdit={openEditDialog}
          onToggleEnabled={handleToggleEnabled}
          onDelete={handleDelete}
        />
      </PixelCard>

      <SourceDetailDrawer
        open={Boolean(selectedSource)}
        source={selectedSource}
        busyAction={busyAction}
        onClose={() => setSelectedSource(null)}
        onSync={async (sourceId) => {
          const source = sources.find((item) => item.id === sourceId);
          if (source) {
            await handleScan(source);
          }
        }}
        onEdit={(source) => {
          setEditingSource(source);
          setDialogOpen(true);
        }}
        onToggleEnabled={async (source) => handleToggleEnabled(source)}
        onDelete={async (source) => handleDelete(source)}
      />

      <SourceFormDialog
        open={dialogOpen}
        source={editingSource}
        submitting={isPending}
        onClose={() => {
          setDialogOpen(false);
          setEditingSource(null);
        }}
        onSubmit={handleCreateOrUpdate}
      />
    </div>
  );
}
