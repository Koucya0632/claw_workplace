import Link from "next/link";

import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import type { DocumentSummary, SearchResultItem } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

interface SearchResultsProps {
  items: SearchResultItem[];
  selectedDocument?: DocumentSummary | null;
  onSelect: (documentId: string) => void;
}

export function SearchResults({ items, selectedDocument, onSelect }: SearchResultsProps) {
  // 搜索頁中央展示結果列表，右側則顯示目前選定文件預覽。
  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
      <PixelCard title="搜索結果" eyebrow="Results">
        <div className="space-y-3">
          {items.length === 0 ? (
            <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
              目前沒有結果，先建立資料源並完成掃描後再搜索。
            </div>
          ) : (
            items.map((item) => (
              <button
                key={item.document_id}
                type="button"
                onClick={() => onSelect(item.document_id)}
                className="w-full border-4 border-ink bg-white p-4 text-left transition hover:-translate-y-1"
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-black tracking-[0.08em]">{item.filename}</h3>
                    <p className="text-xs text-slate-500">{item.relative_path}</p>
                  </div>
                  <StatusPill status={item.matched_on === "content" ? "completed" : "ready"} />
                </div>
                <p className="mb-3 text-sm leading-6 text-slate-700">{item.snippet}</p>
                <div className="flex flex-wrap items-center gap-3 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                  <span>{item.source_name}</span>
                  <span>{formatDateTime(item.modified_at)}</span>
                </div>
              </button>
            ))
          )}
        </div>
      </PixelCard>

      <PixelCard title="文件預覽" eyebrow="Preview">
        {selectedDocument ? (
          <div className="space-y-4">
            <div className="border-4 border-ink bg-sand p-4">
              <h3 className="text-sm font-black tracking-[0.08em]">{selectedDocument.filename}</h3>
              <p className="mt-2 text-xs text-slate-600">{selectedDocument.relative_path}</p>
              <p className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-500">
                {selectedDocument.extension} · {formatDateTime(selectedDocument.modified_at)}
              </p>
            </div>
            <pre className={cn("pixel-scrollbar max-h-[420px] overflow-auto border-4 border-ink bg-white p-4 text-sm leading-6 whitespace-pre-wrap")}>
              {selectedDocument.extracted_text || selectedDocument.content_preview}
            </pre>
            <Link
              href={`/analysis?documentId=${selectedDocument.id}`}
              className="pixel-button inline-flex bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
            >
              進入摘要分析
            </Link>
          </div>
        ) : (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            點擊左側結果卡即可查看全文預覽與摘要入口。
          </div>
        )}
      </PixelCard>
    </div>
  );
}

