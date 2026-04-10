"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import {
  fetchDocumentVersions,
  fetchKnowledgeIngestionRuns,
  fetchSources,
  ingestKnowledge,
  scanSource
} from "@/lib/api";
import type {
  BusinessType,
  DocumentVersionSummary,
  KnowledgeIngestRequest,
  KnowledgeIngestionItemResponse,
  KnowledgeIngestionRunResponse,
  SourceResponse
} from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const KNOWLEDGE_ROLES = [
  { name: "Controller", tagline: "任務入口", status: "running", quote: "我會決定何時讓 support-agent 啟動知識接入，而不是只查既有索引。" },
  { name: "Support Agent", tagline: "資料接入與沉澱", status: "ready", quote: "我會搜尋候選來源、判斷可信度與相關性，並把高價值內容沉澱進知識庫。" },
  { name: "Knowledge Store", tagline: "既有索引主線", status: "ready", quote: "我沿用 documents、chunks 與 FTS，保留 tags、版本鏈與 provenance。" },
  { name: "Refresh Loop", tagline: "更新與回查", status: "pending", quote: "同 canonical URL 的內容更新會走版本化，不會把知識庫塞滿重複文件。" }
];

const DEFAULT_FORM: KnowledgeIngestRequest = {
  topic: "",
  query: "",
  source_name: "",
  source_type: "web_page",
  urls: [],
  domains: [],
  keywords: [],
  must_include: [],
  must_exclude: [],
  business_type: null,
  time_window_days: null,
  limit: 5,
  auto_publish: true
};

const BUSINESS_TYPES: Array<{ value: BusinessType; label: string }> = [
  { value: "support", label: "Support" },
  { value: "product", label: "Product" },
  { value: "engineering", label: "Engineering" },
  { value: "compliance", label: "Compliance" },
  { value: "operations", label: "Operations" },
  { value: "market", label: "Market" },
  { value: "finance", label: "Finance" },
  { value: "security", label: "Security" }
];

function toLines(value: string[]) {
  return value.join("\n");
}

function fromLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : [];
}

function asOptionalBusinessType(value: unknown): BusinessType | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  return value as BusinessType;
}

function buildFormFromSource(source: SourceResponse): KnowledgeIngestRequest {
  const extra = source.config.extra ?? {};
  const urls = [
    ...(source.config.url ? [source.config.url] : []),
    ...((source.config.urls ?? []).filter(Boolean))
  ];

  return {
    topic: source.name,
    query: typeof extra.query === "string" ? extra.query : source.name,
    source_id: source.id,
    source_name: source.name,
    source_type: source.type === "url_list" || source.type === "rss_feed" ? source.type : "web_page",
    urls,
    domains: asStringArray(extra.domains),
    keywords: asStringArray(extra.keywords),
    must_include: asStringArray(extra.must_include),
    must_exclude: asStringArray(extra.must_exclude),
    business_type: asOptionalBusinessType(extra.business_type),
    time_window_days: typeof extra.time_window_days === "number" ? extra.time_window_days : null,
    limit: Math.max(1, Math.min(20, urls.length || 5)),
    auto_publish: true
  };
}

export default function OpenClawKnowledgePage() {
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [form, setForm] = useState<KnowledgeIngestRequest>(DEFAULT_FORM);
  const [runs, setRuns] = useState<KnowledgeIngestionRunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<KnowledgeIngestionRunResponse | null>(null);
  const [selectedItem, setSelectedItem] = useState<KnowledgeIngestionItemResponse | null>(null);
  const [versions, setVersions] = useState<DocumentVersionSummary[]>([]);
  const [message, setMessage] = useState("support-agent 現在可以把外部資料整理後沉澱進既有知識庫，並保留 tags、版本鏈與 provenance。");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  const externalSources = useMemo(
    () => sources.filter((source) => ["web_page", "rss_feed", "url_list"].includes(source.type)),
    [sources]
  );

  async function reloadSources() {
    const nextSources = await fetchSources();
    setSources(nextSources);
    return nextSources;
  }

  async function reloadRuns(sourceId?: string) {
    const nextRuns = await fetchKnowledgeIngestionRuns({ sourceId, limit: 12 });
    setRuns(nextRuns);
    setActiveRun((current) => {
      if (!current) return nextRuns[0] ?? null;
      return nextRuns.find((run) => run.id === current.id) ?? nextRuns[0] ?? null;
    });
    return nextRuns;
  }

  useEffect(() => {
    startTransition(async () => {
      try {
        const nextSources = await reloadSources();
        const nextRuns = await reloadRuns();
        if (nextSources.length === 0) {
          setMessage("目前尚未建立外部知識來源；你也可以直接在下方表單用 ad-hoc 模式接入。");
        } else if (nextRuns.length === 0) {
          setMessage("已載入現有資料源。選一個 source 重整，或直接用下方表單做一次新接入。");
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 Knowledge 管理資料");
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!activeRun) {
      setSelectedItem(null);
      setVersions([]);
      return;
    }
    const firstDocumentItem = activeRun.items.find((item) => item.document_id) ?? activeRun.items[0] ?? null;
    setSelectedItem(firstDocumentItem);
  }, [activeRun]);

  useEffect(() => {
    if (!selectedItem?.document_id) {
      setVersions([]);
      return;
    }
    startTransition(async () => {
      try {
        setVersions(await fetchDocumentVersions(selectedItem.document_id!));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入文件版本鏈");
      }
    });
  }, [selectedItem, startTransition]);

  function handleSourceSelect(sourceId: string) {
    setSelectedSourceId(sourceId);
    if (!sourceId) {
      setForm(DEFAULT_FORM);
      setMessage("已切回 ad-hoc 模式。這次接入會自動建立新的 reusable source。");
      return;
    }
    const selectedSource = externalSources.find((source) => source.id === sourceId);
    if (!selectedSource) return;
    setForm(buildFormFromSource(selectedSource));
    setMessage(`已載入來源「${selectedSource.name}」，可直接重整，也可微調條件後重新接入。`);
  }

  function updateListField(key: keyof KnowledgeIngestRequest, value: string) {
    setForm((current) => ({ ...current, [key]: fromLines(value) }));
  }

  async function handleIngest() {
    setError("");
    setMessage("正在執行 support-agent 知識接入...");
    startTransition(async () => {
      try {
        const run = await ingestKnowledge({
          ...form,
          source_id: selectedSourceId || form.source_id || undefined,
          source_name: form.source_name?.trim() || undefined,
          query: form.query?.trim() || "",
          topic: form.topic.trim()
        });
        setActiveRun(run);
        setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)].slice(0, 12));
        await reloadSources();
        setMessage(`接入完成：accepted ${run.accepted_count} / updated ${run.updated_count} / rejected ${run.rejected_count}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "知識接入失敗");
      }
    });
  }

  async function handleRefreshSource(sourceId: string) {
    setError("");
    setMessage("正在依既有 source 設定重整知識...");
    startTransition(async () => {
      try {
        await scanSource(sourceId);
        const nextRuns = await reloadRuns(sourceId);
        await reloadSources();
        setActiveRun(nextRuns[0] ?? null);
        setMessage("來源重整完成，已更新最新接入結果。");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "來源重整失敗");
      }
    });
  }

  return (
    <OpenClawPageShell
      title="Knowledge Ingestion"
      description="Knowledge Ingestion 是 OpenClaw Control Center 內的 Admin Tools 分區，主要查看搜尋即入庫結果、手動接入紀錄、來源重整與文件版本鏈。"
      roles={KNOWLEDGE_ROLES}
      sectionGroup="Admin Tools"
      sectionLabel="Knowledge Ingestion"
    >
      <PixelCard title="接入工作台" eyebrow="Ingest">
        <div className="border-4 border-ink bg-white px-4 py-3 text-sm leading-7 text-slate-700">
          {error ? <span className="text-coral">{error}</span> : message}
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-4">
            <label className="space-y-2">
              <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Reusable Source</span>
              <select
                value={selectedSourceId}
                onChange={(event) => handleSourceSelect(event.target.value)}
                className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              >
                <option value="">Ad-hoc 接入（自動建立新 source）</option>
                {externalSources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name} · {source.type}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid gap-3">
              {externalSources.length === 0 ? (
                <div className="border-4 border-dashed border-slate-300 bg-white px-4 py-5 text-sm text-slate-500">
                  尚無外部知識來源，第一次手動接入後就會自動生成 reusable source。
                </div>
              ) : (
                externalSources.map((source) => (
                  <article key={source.id} className="border-4 border-ink bg-white px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-black tracking-[0.08em]">{source.name}</p>
                        <p className="mt-1 text-xs text-slate-500">{source.type} · {source.id}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRefreshSource(source.id)}
                        disabled={isPending}
                        className="pixel-button bg-ink px-3 py-2 text-[11px] font-black tracking-[0.08em] text-sand disabled:opacity-60"
                      >
                        重整
                      </button>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">最後掃描：{formatDateTime(source.last_scan_at)}</p>
                  </article>
                ))
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_220px]">
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">主題</span>
                <input value={form.topic} onChange={(event) => setForm((current) => ({ ...current, topic: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Source 類型</span>
                <select value={form.source_type} onChange={(event) => setForm((current) => ({ ...current, source_type: event.target.value as KnowledgeIngestRequest["source_type"] }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none">
                  <option value="web_page">web_page</option>
                  <option value="url_list">url_list</option>
                  <option value="rss_feed">rss_feed</option>
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Business Type</span>
                <select value={form.business_type ?? ""} onChange={(event) => setForm((current) => ({ ...current, business_type: (event.target.value || null) as BusinessType | null }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none">
                  <option value="">未指定</option>
                  {BUSINESS_TYPES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_160px_160px]">
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Source 名稱</span>
                <input value={form.source_name ?? ""} onChange={(event) => setForm((current) => ({ ...current, source_name: event.target.value }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Time Window Days</span>
                <input type="number" min={1} max={365} value={form.time_window_days ?? ""} onChange={(event) => setForm((current) => ({ ...current, time_window_days: event.target.value ? Number(event.target.value) : null }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Limit</span>
                <input type="number" min={1} max={20} value={form.limit} onChange={(event) => setForm((current) => ({ ...current, limit: Number(event.target.value) || 5 }))} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none" />
              </label>
              <label className="flex items-center gap-3 border-4 border-ink bg-sand px-4 py-3">
                <input type="checkbox" checked={form.auto_publish} onChange={(event) => setForm((current) => ({ ...current, auto_publish: event.target.checked }))} className="h-4 w-4" />
                <span className="text-sm font-black tracking-[0.08em]">自動入庫</span>
              </label>
            </div>

            <label className="space-y-2">
              <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">搜尋查詢</span>
              <textarea value={form.query ?? ""} onChange={(event) => setForm((current) => ({ ...current, query: event.target.value }))} rows={2} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
            </label>

            <div className="grid gap-4 xl:grid-cols-2">
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">URLs</span>
                <textarea value={toLines(form.urls)} onChange={(event) => updateListField("urls", event.target.value)} rows={5} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Domains</span>
                <textarea value={toLines(form.domains)} onChange={(event) => updateListField("domains", event.target.value)} rows={5} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Keywords</span>
                <textarea value={toLines(form.keywords)} onChange={(event) => updateListField("keywords", event.target.value)} rows={4} className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
              </label>
              <label className="space-y-2">
                <span className="text-[11px] font-black tracking-[0.12em] text-slate-500">Must Include / Exclude</span>
                <div className="grid gap-3">
                  <textarea value={toLines(form.must_include)} onChange={(event) => updateListField("must_include", event.target.value)} rows={2} placeholder="每行一個必須包含詞" className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
                  <textarea value={toLines(form.must_exclude)} onChange={(event) => updateListField("must_exclude", event.target.value)} rows={2} placeholder="每行一個排除詞" className="w-full border-4 border-ink bg-white px-4 py-3 text-sm leading-7 outline-none" />
                </div>
              </label>
            </div>

            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={handleIngest} disabled={isPending || !form.topic.trim() || !(form.source_name ?? "").trim()} className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60">
                {isPending ? "接入中..." : "執行 Knowledge Ingest"}
              </button>
              <button type="button" onClick={() => handleSourceSelect("")} disabled={isPending} className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60">
                清空表單
              </button>
            </div>
          </div>
        </div>
      </PixelCard>

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <PixelCard title="最近接入批次" eyebrow="Runs">
          {runs.length === 0 ? (
            <div className="border-4 border-dashed border-slate-300 bg-white px-4 py-5 text-sm text-slate-500">
              尚無 knowledge ingestion run，先從上方表單執行一次接入。
            </div>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => setActiveRun(run)}
                  className={`w-full border-4 px-4 py-4 text-left ${activeRun?.id === run.id ? "border-ink bg-sand" : "border-slate-300 bg-white"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-black tracking-[0.08em]">{run.topic}</p>
                      <p className="mt-1 text-xs text-slate-500">{run.source_name} · {formatDateTime(run.created_at)}</p>
                    </div>
                    <span className="border-2 border-ink px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em]">{run.status}</span>
                  </div>
                  <p className="mt-3 text-xs text-slate-600">
                    accepted {run.accepted_count} / updated {run.updated_count} / rejected {run.rejected_count}
                  </p>
                </button>
              ))}
            </div>
          )}
        </PixelCard>

        <div className="space-y-5">
          <PixelCard title="Run 詳情" eyebrow="Details">
            {!activeRun ? (
              <div className="border-4 border-dashed border-slate-300 bg-white px-4 py-5 text-sm text-slate-500">
                選一個 run 查看接入結果、拒收原因與版本鏈。
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-4">
                  <article className="border-4 border-ink bg-white px-4 py-3">
                    <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">Candidates</p>
                    <p className="mt-2 text-2xl font-black">{activeRun.total_candidates}</p>
                  </article>
                  <article className="border-4 border-ink bg-white px-4 py-3">
                    <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">Accepted</p>
                    <p className="mt-2 text-2xl font-black">{activeRun.accepted_count}</p>
                  </article>
                  <article className="border-4 border-ink bg-white px-4 py-3">
                    <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">Updated</p>
                    <p className="mt-2 text-2xl font-black">{activeRun.updated_count}</p>
                  </article>
                  <article className="border-4 border-ink bg-white px-4 py-3">
                    <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">Rejected</p>
                    <p className="mt-2 text-2xl font-black">{activeRun.rejected_count}</p>
                  </article>
                </div>

                <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
                  <div className="space-y-3">
                    {activeRun.items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setSelectedItem(item)}
                        className={`w-full border-4 px-4 py-4 text-left ${selectedItem?.id === item.id ? "border-ink bg-sand" : "border-slate-300 bg-white"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-black tracking-[0.08em]">{item.title || item.candidate_url}</p>
                            <p className="mt-1 text-xs text-slate-500">{item.source_domain || item.candidate_url}</p>
                          </div>
                          <span className="border-2 border-ink px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em]">{item.status}</span>
                        </div>
                        <p className="mt-3 text-xs text-slate-600">
                          trust {item.trust_score ?? "-"} · relevance {item.relevance_score ?? "-"} · duplicate {item.duplicate_score ?? "-"}
                        </p>
                        {item.reject_reason ? (
                          <p className="mt-2 text-xs text-coral">{item.reject_reason}</p>
                        ) : null}
                      </button>
                    ))}
                  </div>

                  <div className="space-y-4">
                    <div className="border-4 border-ink bg-white px-4 py-4">
                      <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">目前選中項目</p>
                      {!selectedItem ? (
                        <p className="mt-3 text-sm text-slate-500">選一筆候選來看文件版本鏈與 metadata。</p>
                      ) : (
                        <div className="mt-3 space-y-2 text-sm text-slate-700">
                          <p className="font-black">{selectedItem.title || selectedItem.candidate_url}</p>
                          <p>URL：{selectedItem.normalized_url ?? selectedItem.candidate_url}</p>
                          <p>Document ID：{selectedItem.document_id ?? "未入庫"}</p>
                        </div>
                      )}
                    </div>

                    <div className="border-4 border-ink bg-white px-4 py-4">
                      <p className="text-[11px] font-black tracking-[0.12em] text-slate-500">版本鏈</p>
                      {versions.length === 0 ? (
                        <p className="mt-3 text-sm text-slate-500">這筆候選目前沒有可顯示的版本資料。</p>
                      ) : (
                        <div className="mt-3 space-y-3">
                          {versions.map((version) => (
                            <article key={version.id} className="border-4 border-slate-300 bg-sand px-3 py-3">
                              <div className="flex items-start justify-between gap-3">
                                <p className="text-sm font-black tracking-[0.08em]">v{version.version_number}</p>
                                <span className="border-2 border-ink px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em]">{version.status ?? "active"}</span>
                              </div>
                              <p className="mt-2 text-xs text-slate-600">{version.filename}</p>
                              <p className="mt-1 text-xs text-slate-500">indexed：{formatDateTime(version.indexed_at)}</p>
                              <p className="mt-1 text-xs text-slate-500 break-all">checksum：{version.checksum}</p>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </PixelCard>
        </div>
      </div>
    </OpenClawPageShell>
  );
}
