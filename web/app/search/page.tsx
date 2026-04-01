"use client";

import { useEffect, useState, useTransition } from "react";

import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";
import { SearchResults } from "@/components/search-results";
import { fetchDocument, fetchSources, searchDocuments } from "@/lib/api";
import type { DocumentSummary, SearchResultItem, SourceResponse } from "@/lib/types";

const SEARCH_ROLES = [
  { name: "Chief Lobster", tagline: "任務調度", status: "running", quote: "請告訴我想找什麼，我會安排搜索路線。" },
  { name: "Search Lobster", tagline: "資料定位", status: "ready", quote: "檔名與全文都可以搜，來源與時間也能篩選。" },
  { name: "Organize Lobster", tagline: "摘要整理", status: "pending", quote: "選定文件後，我再接手後續摘要。" },
  { name: "Analyze Lobster", tagline: "多文件分析", status: "disabled", quote: "多文件語意分析會在 Phase 2 啟用。" },
  { name: "Report Lobster", tagline: "報告輸出", status: "disabled", quote: "先完成摘要任務，報告頁就會接棒。" }
];

export default function SearchPage() {
  // 搜索頁需要同時管理來源清單、查詢條件、結果與預覽文件。
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [query, setQuery] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("先建立資料源並完成掃描，再輸入關鍵字搜索。");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        setSources(await fetchSources());
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入資料源");
      }
    });
  }, [startTransition]);

  async function runSearch() {
    // 搜索前先清掉舊錯誤，避免使用者被過期訊息干擾。
    setError("");
    setHint("");

    startTransition(async () => {
      try {
        const response = await searchDocuments({
          query,
          source_id: sourceId || undefined,
          mode: "all"
        });
        setResults(response.items);
        setSelectedDocument(null);
        setHint(
          response.total > 0
            ? `找到 ${response.total} 筆結果，首批回應 ${response.query_time_ms} ms。`
            : "目前沒有符合結果，請調整關鍵字或重新掃描資料源。"
        );
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "搜索失敗");
      }
    });
  }

  async function handleSelect(documentId: string) {
    // 點擊結果卡後再抓全文，避免首輪搜索就載入所有文件內容。
    setError("");

    try {
      setSelectedDocument(await fetchDocument(documentId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "無法載入文件");
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <RoleSquad roles={SEARCH_ROLES} />

      <section className="space-y-5">
        <PixelCard title="搜索控制台" eyebrow="Search">
          <div className="grid gap-4 lg:grid-cols-[1fr_240px_auto]">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="輸入檔名、專案名、會議重點或數據關鍵字"
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            />
            <select
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            >
              <option value="">全部資料源</option>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={runSearch}
              disabled={!query.trim() || isPending}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPending ? "搜索中..." : "開始搜索"}
            </button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="border-4 border-ink bg-sand p-4 text-sm text-slate-700">
              支援檔名搜索、全文搜索、來源過濾與時間欄位保留。語意搜索介面已預留，Phase 1 尚未啟用。
            </div>
            <div className="border-4 border-ink bg-white p-4 text-sm text-slate-700">
              {error ? <span className="text-coral">{error}</span> : hint}
            </div>
          </div>
        </PixelCard>

        <SearchResults items={results} selectedDocument={selectedDocument} onSelect={handleSelect} />
      </section>
    </div>
  );
}
