import { PixelCard } from "@/components/pixel-card";
import type { TaskStatusResponse } from "@/lib/types";

interface ReportPreviewProps {
  task?: TaskStatusResponse | null;
}

export function ReportPreview({ task }: ReportPreviewProps) {
  // 報告頁下方直接渲染 Markdown 原文，讓使用者匯出前先確認內容。
  return (
    <PixelCard title="Markdown 預覽" eyebrow="Export">
      {task?.result_payload ? (
        <pre className="pixel-scrollbar max-h-[520px] overflow-auto border-4 border-ink bg-white p-4 text-sm leading-6 whitespace-pre-wrap">
          {task.result_payload.markdown}
        </pre>
      ) : (
        <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
          先完成摘要任務，這裡才會出現可匯出的 Markdown。
        </div>
      )}
    </PixelCard>
  );
}

