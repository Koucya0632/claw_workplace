"use client";

import { useEffect, useState, useTransition } from "react";

import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";
import { SourceStatusBoard } from "@/components/source-status-board";
import { createLocalSource, fetchSources, scanSource } from "@/lib/api";
import type { SourceResponse } from "@/lib/types";

const SETTINGS_ROLES = [
  { name: "Chief Lobster", tagline: "接入配置", status: "running", quote: "我會先確認本地資料夾是否合法，再安排掃描。" },
  { name: "Search Lobster", tagline: "索引建立", status: "ready", quote: "掃描完成後，我就能用 FTS5 搜索文本內容。" },
  { name: "Organize Lobster", tagline: "摘要待命", status: "pending", quote: "等索引好了，我就能接手單文件摘要。" },
  { name: "Google Drive", tagline: "雲端預留", status: "disabled", quote: "接口已預留，Phase 1 不開啟真接入。" },
  { name: "Notion", tagline: "雲端預留", status: "disabled", quote: "資料模型與 UI 已預留，等待後續接入。" }
];

export default function SourceSettingsPage() {
  // 設定頁負責建立本地資料源與手動掃描，因此要同步來源列表與當前操作狀態。
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [name, setName] = useState("OpenClaw 範例資料夾");
  const [path, setPath] = useState("./samples/local_source");
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function loadSources() {
    // 來源清單會在建立與掃描後重抓一次，確保狀態顯示同步。
    setSources(await fetchSources());
  }

  useEffect(() => {
    startTransition(async () => {
      try {
        await loadSources();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入資料源");
      }
    });
  }, [startTransition]);

  async function handleCreateSource() {
    // 建立來源後立刻刷新清單，讓使用者看得到最新狀態。
    setError("");
    setMessage("");

    startTransition(async () => {
      try {
        const source = await createLocalSource(name, path);
        await loadSources();
        setMessage(`已建立資料源：${source.name}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立資料源失敗");
      }
    });
  }

  async function handleScan(sourceId: string) {
    // 掃描時記錄 busySourceId，讓對應按鈕顯示 loading 狀態。
    setBusySourceId(sourceId);
    setError("");
    setMessage("");

    try {
      const result = await scanSource(sourceId);
      await loadSources();
      setMessage(`掃描完成：成功 ${result.scanned_count}，略過 ${result.skipped_count}`);
      if (result.errors.length > 0) {
        setError(result.errors.join("；"));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "掃描失敗");
    } finally {
      setBusySourceId(null);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <RoleSquad roles={SETTINGS_ROLES} />

      <section className="space-y-5">
        <PixelCard title="本地資料源接入" eyebrow="Settings">
          <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr_auto]">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="資料源名稱"
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
            <input
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="資料夾路徑"
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
            <button
              type="button"
              onClick={handleCreateSource}
              disabled={isPending}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              新增來源
            </button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="border-4 border-ink bg-sand p-4 text-sm leading-7 text-slate-700">
              Phase 1 僅允許本地資料夾，且必須位於後端設定的允許根目錄內。
            </div>
            <div className="border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
              {error ? <span className="text-coral">{error}</span> : message || "建立來源後請手動執行掃描。"}
            </div>
          </div>
        </PixelCard>

        <SourceStatusBoard sources={sources} onScan={handleScan} busySourceId={busySourceId} />

        <PixelCard title="預留雲端 Connector" eyebrow="Planned">
          <div className="grid gap-4 md:grid-cols-2">
            <article className="border-4 border-ink bg-white p-4">
              <h3 className="text-sm font-black tracking-[0.08em]">Google Drive</h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                Connector interface、schema 與 disabled UI 已預留；OAuth 與檔案同步留到 Phase 2。
              </p>
            </article>
            <article className="border-4 border-ink bg-white p-4">
              <h3 className="text-sm font-black tracking-[0.08em]">Notion</h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                Phase 1 只固定資料型別與顯示位置，避免未來接入時重做設定頁結構。
              </p>
            </article>
          </div>
        </PixelCard>
      </section>
    </div>
  );
}
