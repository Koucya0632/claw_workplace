import { PixelCard } from "@/components/pixel-card";
import type { WorkflowRunResponse } from "@/lib/types";

interface WorkflowReportPanelProps {
  run?: WorkflowRunResponse | null;
  onExportMarkdown?: () => void;
  onContinueToReport?: () => void;
  continueDisabled?: boolean;
}

export function WorkflowReportPanel({
  run,
  onExportMarkdown,
  onContinueToReport,
  continueDisabled = false
}: WorkflowReportPanelProps) {
  // 最終報告同時要照顧頁面閱讀與 Markdown 匯出，因此把兩種視圖放在同一個面板。
  const report = run?.final_report;
  const webResult = run?.final_web_result;

  return (
    <PixelCard title={report ? "最終報告" : webResult ? "Web Search 結果" : "最終結果"} eyebrow="Result">
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
      ) : webResult ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-4 border-ink bg-sand p-4">
            <div>
              <h3 className="text-lg font-black tracking-[0.08em]">{webResult.title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-700">{webResult.summary}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {onContinueToReport ? (
                <button
                  type="button"
                  onClick={onContinueToReport}
                  disabled={continueDisabled}
                  className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60"
                >
                  送入分析/報告
                </button>
              ) : null}
              <button
                type="button"
                onClick={onExportMarkdown}
                className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
              >
                匯出 Markdown
              </button>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">重點整理</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {webResult.key_points.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">重點回答</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {webResult.focus_answers.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">格式化輸出</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {webResult.structured_output}
                </pre>
              </article>
            </div>

            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">保留來源</h4>
                <div className="mt-3 space-y-3">
                  {webResult.included_sources.map((item) => (
                    <div key={`${item.source_type}-${item.url ?? item.document_id ?? item.title}`} className="border-4 border-ink bg-sand p-3 text-sm">
                      <p className="font-black">{item.title}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">
                        {item.source_type}
                        {item.domain ? ` / ${item.domain}` : ""}
                      </p>
                      <p className="mt-2 leading-7">{item.snippet}</p>
                      <p className="mt-2 text-xs text-slate-500">{item.reason}</p>
                    </div>
                  ))}
                </div>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">套用條件</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {webResult.applied_filters.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">Markdown</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {webResult.markdown}
                </pre>
              </article>
            </div>
          </div>
        </div>
      ) : (
        <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
          任務尚未完成。完成後這裡會顯示結構化報告或 Web Search 整理結果。
        </div>
      )}
    </PixelCard>
  );
}
