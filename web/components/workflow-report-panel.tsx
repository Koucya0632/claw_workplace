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
  const newsBrief = run?.final_news_brief;
  const systemInspection = run?.final_system_inspection;

  return (
    <PixelCard title={report ? "最終報告" : webResult ? "Web Search 結果" : systemInspection ? "巡檢報告" : "最終結果"} eyebrow="Result">
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
              {webResult.ingest_result ? (
                <article className="border-4 border-ink bg-white p-4">
                  <h4 className="text-sm font-black tracking-[0.08em]">入庫摘要</h4>
                  <p className="mt-3 text-sm leading-7">{webResult.ingest_result.ingest_summary}</p>
                  <ul className="mt-3 space-y-2 text-sm leading-7">
                    <li>來源處理：{webResult.ingest_result.source_resolution}</li>
                    {webResult.ingest_result.source_name ? <li>知識來源：{webResult.ingest_result.source_name}</li> : null}
                    {webResult.ingest_result.ingestion_run_id ? <li>Ingestion Run：{webResult.ingest_result.ingestion_run_id}</li> : null}
                    {webResult.ingest_result.created_source_id ? <li>新建 Source：{webResult.ingest_result.created_source_id}</li> : null}
                    {webResult.ingest_result.merged_source_id ? <li>合併 Source：{webResult.ingest_result.merged_source_id}</li> : null}
                    <li>新增文件：{webResult.ingest_result.stored_documents.length}</li>
                    <li>更新文件：{webResult.ingest_result.updated_documents.length}</li>
                    <li>拒收來源：{webResult.ingest_result.rejected_documents.length}</li>
                  </ul>
                </article>
              ) : null}
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">Markdown</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {webResult.markdown}
                </pre>
              </article>
            </div>
          </div>
        </div>
      ) : newsBrief ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-4 border-ink bg-sand p-4">
            <div>
              <h3 className="text-lg font-black tracking-[0.08em]">{newsBrief.title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-700">{newsBrief.trend_summary}</p>
            </div>
            <div className="flex flex-wrap gap-2">
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
                <h4 className="text-sm font-black tracking-[0.08em]">今日最重要新聞</h4>
                <div className="mt-3 space-y-3">
                  {newsBrief.top_stories.map((item) => (
                    <div key={item.event_key || item.title} className="border-4 border-ink bg-sand p-3 text-sm">
                      <p className="font-black">{item.title}</p>
                      <p className="mt-2 leading-7">{item.summary}</p>
                      <p className="mt-2 text-xs text-slate-500">重要原因：{item.importance_reason}</p>
                      {item.possible_impact ? <p className="mt-1 text-xs text-slate-500">可能影響：{item.possible_impact}</p> : null}
                    </div>
                  ))}
                </div>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">其他值得關注</h4>
                <div className="mt-3 space-y-3">
                  {newsBrief.other_stories.map((item) => (
                    <div key={item.event_key || item.title} className="border-4 border-ink bg-sand p-3 text-sm">
                      <p className="font-black">{item.title}</p>
                      <p className="mt-2 leading-7">{item.summary}</p>
                    </div>
                  ))}
                </div>
              </article>
            </div>

            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">今日總結</h4>
                <p className="mt-3 text-sm leading-7">{newsBrief.trend_summary}</p>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {newsBrief.watch_items.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">投遞狀態</h4>
                <p className="mt-3 text-sm leading-7">狀態：{newsBrief.delivery_status}</p>
                {newsBrief.delivery_target ? <p className="mt-2 text-sm leading-7">目標：{newsBrief.delivery_target}</p> : null}
                {newsBrief.delivery_error ? <p className="mt-2 text-sm leading-7 text-coral">{newsBrief.delivery_error}</p> : null}
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">Markdown</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {newsBrief.markdown}
                </pre>
              </article>
            </div>
          </div>
        </div>
      ) : systemInspection ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-4 border-ink bg-sand p-4">
            <div>
              <h3 className="text-lg font-black tracking-[0.08em]">{systemInspection.title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-700">
                升級建議：{systemInspection.version_update_check.upgrade_recommendation}
              </p>
            </div>
            <button
              type="button"
              onClick={onExportMarkdown}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
            >
              匯出 Markdown
            </button>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">巡檢總結</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {systemInspection.inspection_summary.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">高優先級風險</h4>
                <div className="mt-3 space-y-3">
                  {systemInspection.high_priority_risks.map((item) => (
                    <div key={item.issue_key} className="border-4 border-ink bg-sand p-3 text-sm">
                      <p className="font-black">{item.description}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.priority.toUpperCase()} / {item.severity.toUpperCase()} / frequency {item.frequency}
                      </p>
                      <ul className="mt-2 space-y-1 leading-6">
                        {item.fix_actions.map((action) => (
                          <li key={action}>- {action}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">建議執行順序</h4>
                <ol className="mt-3 space-y-2 text-sm leading-7">
                  {systemInspection.recommended_execution_order.map((item, index) => (
                    <li key={item}>{index + 1}. {item}</li>
                  ))}
                </ol>
              </article>
            </div>

            <div className="space-y-4">
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">版本更新檢查</h4>
                <p className="mt-3 text-sm leading-7">目前版本：{systemInspection.version_update_check.current_version}</p>
                <p className="mt-1 text-sm leading-7">最新版本：{systemInspection.version_update_check.latest_version ?? "unknown"}</p>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {systemInspection.version_update_check.compatibility_risks.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">修復與優化建議</h4>
                <ul className="mt-3 space-y-2 text-sm leading-7">
                  {systemInspection.fix_and_optimization_actions.map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">Telegram 摘要</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[220px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {systemInspection.telegram_summary}
                </pre>
                <p className="mt-3 text-sm leading-7">投遞狀態：{systemInspection.delivery_status}</p>
                {systemInspection.delivery_target ? <p className="mt-1 text-sm leading-7">目標：{systemInspection.delivery_target}</p> : null}
                {systemInspection.delivery_error ? <p className="mt-1 text-sm leading-7 text-coral">{systemInspection.delivery_error}</p> : null}
              </article>
              <article className="border-4 border-ink bg-white p-4">
                <h4 className="text-sm font-black tracking-[0.08em]">Markdown</h4>
                <pre className="pixel-scrollbar mt-3 max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
                  {systemInspection.markdown}
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
