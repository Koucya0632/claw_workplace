import { PixelCard } from "@/components/pixel-card";
import type { WorkflowRunResponse } from "@/lib/types";

interface WorkflowReportPanelProps {
  run?: WorkflowRunResponse | null;
  onExportMarkdown?: () => void;
}

export function WorkflowReportPanel({ run, onExportMarkdown }: WorkflowReportPanelProps) {
  // 最終報告同時要照顧頁面閱讀與 Markdown 匯出，因此把兩種視圖放在同一個面板。
  const report = run?.final_report;

  return (
    <PixelCard title="最終報告" eyebrow="Report">
      {report ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-4 border-ink bg-sand p-4">
            <div>
              <h3 className="text-lg font-black tracking-[0.08em]">{report.title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-700">{report.executive_summary}</p>
            </div>
            <button
              type="button"
              onClick={onExportMarkdown}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
            >
              匯出 Markdown
            </button>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">重點</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {report.highlights.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">建議</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {report.recommendations.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">章節</h4>
                <div className="mt-3 space-y-4">
                  {report.sections.map((section) => (
                    <section key={section.title} className="border-4 border-ink bg-sand p-3">
                      <h5 className="text-sm font-black tracking-[0.08em]">{section.title}</h5>
                      {section.summary ? <p className="mt-2 text-sm leading-7">{section.summary}</p> : null}
                      {section.bullets.length > 0 ? (
                        <ul className="mt-2 space-y-2 text-sm leading-7">
                          {section.bullets.map((item) => (
                            <li key={item}>- {item}</li>
                          ))}
                        </ul>
                      ) : null}
                      {section.body ? <p className="mt-2 text-sm leading-7">{section.body}</p> : null}
                    </section>
                  ))}
                </div>
              </article>
            </div>

            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">引用證據</h4>
                <div className="mt-3 space-y-3">
                  {report.evidence.map((item) => (
                    <div key={`${item.document_id}-${item.quote}`} className="border-4 border-ink bg-sand p-3 text-sm">
                      <p className="font-black">{item.filename}</p>
                      <p className="mt-2 leading-7">{item.quote}</p>
                      <p className="mt-2 text-xs text-slate-500">{item.reason}</p>
                    </div>
                  ))}
                </div>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">附錄</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {report.appendix.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">Markdown</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {report.markdown}
                </pre>
              </article>
            </div>
          </div>
        </div>
      ) : (
        <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
          報告階段尚未完成。完成後這裡會顯示結構化報告與 Markdown。
        </div>
      )}
    </PixelCard>
  );
}
