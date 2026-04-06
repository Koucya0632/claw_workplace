"use client";

import { useEffect, useMemo, useState } from "react";

import type { SourceResponse, SourceType } from "@/lib/types";

type SourceFormPayload = {
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
};

interface SourceFormDialogProps {
  open: boolean;
  source?: SourceResponse | null;
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (payload: SourceFormPayload) => Promise<void> | void;
}

const SOURCE_TYPE_OPTIONS: Array<{ value: SourceType; label: string }> = [
  { value: "local", label: "Local Folder" },
  { value: "web_page", label: "Web Page" },
  { value: "url_list", label: "URL List" },
  { value: "rss_feed", label: "RSS Feed" },
  { value: "google_drive", label: "Google Drive" },
  { value: "notion", label: "Notion" }
];

export function SourceFormDialog({ open, source, submitting = false, onClose, onSubmit }: SourceFormDialogProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<SourceType>("local");
  const [path, setPath] = useState("");
  const [url, setUrl] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [rootPageId, setRootPageId] = useState("");
  const [databaseId, setDatabaseId] = useState("");
  const [extraText, setExtraText] = useState("{}");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }
    setError("");
    setName(source?.name ?? "");
    setType(source?.type ?? "local");
    setPath(source?.config.path ?? "");
    setUrl(source?.config.url ?? "");
    setUrlsText(source?.config.urls?.join("\n") ?? "");
    setWorkspaceName(source?.config.workspace_name ?? "");
    setRootPageId(source?.config.root_page_id ?? "");
    setDatabaseId(source?.config.database_id ?? "");
    setExtraText(JSON.stringify(source?.config.extra ?? {}, null, 2));
  }, [open, source]);

  const title = source ? "編輯資料源" : "新增資料源";
  const buttonLabel = source ? "儲存變更" : "建立資料源";
  const showSingleUrl = type === "web_page" || type === "rss_feed";
  const showUrlList = type === "url_list";
  const showPath = type === "local";
  const showDriveFields = type === "google_drive";
  const showNotionFields = type === "notion";

  const helperText = useMemo(() => {
    if (type === "local") return "指定允許根目錄內的本地資料夾。";
    if (type === "web_page") return "適合單一權威頁面或下載頁。";
    if (type === "url_list") return "每行一個 URL，適合固定來源清單。";
    if (type === "rss_feed") return "輸入 RSS/Atom feed URL。";
    if (type === "google_drive") return "先填 workspace 與額外設定，第二階段可再補 OAuth。";
    return "可填 root page / database id 與額外 JSON 設定。";
  }, [type]);

  if (!open) {
    return null;
  }

  async function handleSubmit() {
    setError("");
    try {
      const extra = extraText.trim() ? (JSON.parse(extraText) as Record<string, unknown>) : {};
      await onSubmit({
        name,
        type,
        config: {
          path: path || null,
          url: url || null,
          urls: urlsText
            .split("\n")
            .map((item) => item.trim())
            .filter(Boolean),
          root_page_id: rootPageId || null,
          database_id: databaseId || null,
          workspace_name: workspaceName || null,
          extra
        }
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "無法儲存資料源");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 px-4 py-8">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto border-4 border-ink bg-paper p-5 shadow-[12px_12px_0_0_#111827]">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Source Form</p>
            <h3 className="mt-2 text-2xl font-black tracking-[0.06em] text-ink">{title}</h3>
            <p className="mt-2 text-sm text-slate-600">{helperText}</p>
          </div>
          <button type="button" onClick={onClose} className="pixel-button bg-slate-100 px-3 py-2 text-xs font-black">
            關閉
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-xs font-black tracking-[0.08em] text-slate-600">名稱</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
              placeholder="例如：OpenClaw 官網更新"
            />
          </label>

          <label className="space-y-2">
            <span className="text-xs font-black tracking-[0.08em] text-slate-600">類型</span>
            <select
              value={type}
              onChange={(event) => setType(event.target.value as SourceType)}
              disabled={Boolean(source)}
              className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
            >
              {SOURCE_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {showPath ? (
            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-black tracking-[0.08em] text-slate-600">資料夾路徑</span>
              <input
                value={path}
                onChange={(event) => setPath(event.target.value)}
                className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
                placeholder="./samples/local_source"
              />
            </label>
          ) : null}

          {showSingleUrl ? (
            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-black tracking-[0.08em] text-slate-600">URL</span>
              <input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
                placeholder="https://example.com/feed"
              />
            </label>
          ) : null}

          {showUrlList ? (
            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-black tracking-[0.08em] text-slate-600">URLs</span>
              <textarea
                value={urlsText}
                onChange={(event) => setUrlsText(event.target.value)}
                className="min-h-32 w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
                placeholder={"https://example.com/a\nhttps://example.com/b"}
              />
            </label>
          ) : null}

          {showDriveFields ? (
            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-black tracking-[0.08em] text-slate-600">Workspace Name</span>
              <input
                value={workspaceName}
                onChange={(event) => setWorkspaceName(event.target.value)}
                className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
                placeholder="Google Drive Workspace"
              />
            </label>
          ) : null}

          {showNotionFields ? (
            <>
              <label className="space-y-2">
                <span className="text-xs font-black tracking-[0.08em] text-slate-600">Root Page ID</span>
                <input
                  value={rootPageId}
                  onChange={(event) => setRootPageId(event.target.value)}
                  className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
                />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-black tracking-[0.08em] text-slate-600">Database ID</span>
                <input
                  value={databaseId}
                  onChange={(event) => setDatabaseId(event.target.value)}
                  className="w-full border-4 border-ink bg-white px-3 py-3 text-sm outline-none"
                />
              </label>
            </>
          ) : null}

          <label className="space-y-2 md:col-span-2">
            <span className="text-xs font-black tracking-[0.08em] text-slate-600">Extra Config (JSON)</span>
            <textarea
              value={extraText}
              onChange={(event) => setExtraText(event.target.value)}
              className="min-h-32 w-full border-4 border-ink bg-white px-3 py-3 font-mono text-xs outline-none"
            />
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-coral">{error}</p>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="pixel-button bg-slate-100 px-4 py-3 text-sm font-black">
              取消
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "儲存中..." : buttonLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
