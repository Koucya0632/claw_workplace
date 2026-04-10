import Link from "next/link";
import type { ReactNode } from "react";

import { PixelCard } from "@/components/pixel-card";
import { inspectWorkflowPayload, summarizeWorkflowRuntimeIssue } from "@/lib/workflow-payloads";
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
  const report = run?.final_report;
  const webResult = run?.final_web_result;
  const newsBrief = run?.final_news_brief;
  const systemInspection = run?.final_system_inspection;
  const developmentReport = run?.final_development_report;
  const developmentDelivery = resolveDevelopmentDelivery(run);
  const errorPreview = run?.error_message ? inspectWorkflowPayload(run.error_message) : null;
  const errorSummary = run?.error_message
    ? summarizeWorkflowRuntimeIssue(run.error_message, workflowContextLabel(run))
    : null;

  return (
    <PixelCard
      title={
        report
          ? "最終報告"
          : webResult
            ? "Web Search 結果"
            : systemInspection
              ? "巡檢報告"
              : developmentReport
                ? "工程任務報告"
                : "最終結果"
      }
      eyebrow="Result"
    >
      {report ? (
        <div className="space-y-4">
          <ResultHero title={report.title} summary={report.executive_summary}>
            {onExportMarkdown ? (
              <ActionButton onClick={onExportMarkdown} tone="coral">
                匯出 Markdown
              </ActionButton>
            ) : null}
          </ResultHero>

          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <SummaryList title="重點" items={report.highlights} />
            <SummaryList title="建議" items={report.recommendations} />
          </div>

          <CollapsibleBlock title="章節詳情">
            <div className="space-y-3">
              {report.sections.map((section) => (
                <article key={section.title} className="border-4 border-ink bg-sand p-3">
                  <h4 className="text-sm font-black tracking-[0.08em]">{section.title}</h4>
                  {section.summary ? <p className="mt-2 text-sm leading-6">{section.summary}</p> : null}
                  {section.bullets.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-sm leading-6">
                      {section.bullets.map((item) => (
                        <li key={item}>- {item}</li>
                      ))}
                    </ul>
                  ) : null}
                  {section.body ? <p className="mt-2 text-sm leading-6">{section.body}</p> : null}
                </article>
              ))}
            </div>
          </CollapsibleBlock>

          <CollapsibleBlock title="引用證據">
            <div className="space-y-3">
              {report.evidence.map((item) => (
                <div key={`${item.document_id}-${item.quote}`} className="border-4 border-ink bg-sand p-3 text-sm">
                  <p className="font-black">{item.filename}</p>
                  <p className="mt-2 leading-6">{item.quote}</p>
                  <p className="mt-2 text-xs text-slate-500">{item.reason}</p>
                </div>
              ))}
            </div>
          </CollapsibleBlock>

          <CollapsibleBlock title="附錄">
            <ul className="space-y-1 text-sm leading-6">
              {report.appendix.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </CollapsibleBlock>

          <MarkdownDetails markdown={report.markdown} />
        </div>
      ) : developmentReport ? (
        <div className="space-y-4">
          <ResultHero title={developmentReport.task_name} summary={developmentReport.final_summary} />

          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <SummaryText title="問題定義" text={developmentReport.problem_definition} />
            <SummaryList title="需求分析" items={developmentReport.requirements_analysis} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <SummaryList title="方案設計" items={developmentReport.solution_design} />
            <SummaryList title="開發成果" items={developmentReport.development_results} />
          </div>

          <CollapsibleBlock title="測試結果">
            <ul className="space-y-1 text-sm leading-6">
              {developmentReport.test_results.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </CollapsibleBlock>

          <CollapsibleBlock title="技術選型">
            <div className="space-y-3">
              {developmentReport.technology_selection.map((item) => (
                <div key={`${item.category}-${item.choice}`} className="border-4 border-ink bg-sand p-3 text-sm">
                  <p className="font-black">{item.category}</p>
                  <p className="mt-2 leading-6">{item.choice}</p>
                  <p className="mt-2 text-xs text-slate-500">{item.reason}</p>
                </div>
              ))}
            </div>
          </CollapsibleBlock>

          <CollapsibleBlock title="任務拆分 / 排期">
            <div className="space-y-3">
              {developmentReport.task_breakdown_schedule.map((item) => (
                <div key={`${item.title}-${item.priority}`} className="border-4 border-ink bg-sand p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-black">{item.title}</p>
                    <span className="text-xs uppercase tracking-[0.12em] text-slate-500">
                      {item.priority} / {item.estimate}
                    </span>
                  </div>
                  <p className="mt-2 leading-6">{item.description}</p>
                </div>
              ))}
            </div>
          </CollapsibleBlock>

          <CollapsibleBlock title="風險與待辦">
            <ul className="space-y-1 text-sm leading-6">
              {developmentReport.risks_and_todos.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </CollapsibleBlock>

          <CollapsibleBlock title="Discord 匯報">
            <div className="space-y-1 text-sm leading-6 text-slate-700">
              <p>狀態：{developmentReport.delivery_status}</p>
              {developmentReport.delivery_target ? <p>目標：{developmentReport.delivery_target}</p> : null}
              <p>來源：{developmentReport.delivery_source}</p>
              {developmentReport.delivery_reason ? <p>說明：{developmentReport.delivery_reason}</p> : null}
              {developmentReport.delivery_error ? <p className="text-coral">{developmentReport.delivery_error}</p> : null}
            </div>
          </CollapsibleBlock>
        </div>
      ) : webResult ? (
        <div className="space-y-4">
          <ResultHero title={webResult.title} summary={webResult.summary}>
            <div className="flex flex-wrap gap-2">
              {onContinueToReport ? (
                <ActionButton onClick={onContinueToReport} disabled={continueDisabled}>
                  送入分析/報告
                </ActionButton>
              ) : null}
              {onExportMarkdown ? (
                <ActionButton onClick={onExportMarkdown} tone="coral">
                  匯出 Markdown
                </ActionButton>
              ) : null}
            </div>
          </ResultHero>

          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <SummaryList title="重點整理" items={webResult.key_points} />
            <SummaryList title="重點回答" items={webResult.focus_answers} />
          </div>

          <CollapsibleBlock title="格式化輸出">
            <pre className="pixel-scrollbar max-h-[320px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
              {webResult.structured_output}
            </pre>
          </CollapsibleBlock>

          <CollapsibleBlock title="保留來源">
            <SourcePreviewList
              sources={webResult.included_sources.map((item) => ({
                key: `${item.source_type}-${item.url ?? item.document_id ?? item.title}`,
                title: item.title,
                meta: `${item.source_type}${item.domain ? ` / ${item.domain}` : ""}`,
                summary: item.snippet,
                note: item.reason
              }))}
            />
          </CollapsibleBlock>

          <CollapsibleBlock title="套用條件">
            <ul className="space-y-1 text-sm leading-6">
              {webResult.applied_filters.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </CollapsibleBlock>

          {webResult.ingest_result ? (
            <CollapsibleBlock title="入庫摘要">
              <div className="space-y-2 text-sm leading-6 text-slate-700">
                <p>{webResult.ingest_result.ingest_summary}</p>
                <ul className="space-y-1">
                  <li>來源處理：{webResult.ingest_result.source_resolution}</li>
                  {webResult.ingest_result.source_name ? <li>知識來源：{webResult.ingest_result.source_name}</li> : null}
                  {webResult.ingest_result.ingestion_run_id ? <li>Ingestion Run：{webResult.ingest_result.ingestion_run_id}</li> : null}
                  {webResult.ingest_result.created_source_id ? <li>新建 Source：{webResult.ingest_result.created_source_id}</li> : null}
                  {webResult.ingest_result.merged_source_id ? <li>合併 Source：{webResult.ingest_result.merged_source_id}</li> : null}
                </ul>
              </div>
            </CollapsibleBlock>
          ) : null}

          <MarkdownDetails markdown={webResult.markdown} />
        </div>
      ) : newsBrief ? (
        <div className="space-y-4">
          <ResultHero title={newsBrief.title} summary={newsBrief.trend_summary}>
            {onExportMarkdown ? (
              <ActionButton onClick={onExportMarkdown} tone="coral">
                匯出 Markdown
              </ActionButton>
            ) : null}
          </ResultHero>

          <StoryPreviewSection
            title="今日最重要新聞"
            stories={newsBrief.top_stories.map((item) => ({
              key: item.event_key || item.title,
              title: item.title,
              summary: item.summary,
              note: item.importance_reason
            }))}
          />

          <CollapsibleBlock title="其他值得關注">
            <StoryPreviewSection
              title=""
              stories={newsBrief.other_stories.map((item) => ({
                key: item.event_key || item.title,
                title: item.title,
                summary: item.summary
              }))}
              nested
            />
          </CollapsibleBlock>

          <CollapsibleBlock title="今日總結">
            <ul className="space-y-1 text-sm leading-6">
              {newsBrief.watch_items.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </CollapsibleBlock>

          <CollapsibleBlock title="投遞狀態">
            <div className="space-y-1 text-sm leading-6 text-slate-700">
              <p>狀態：{newsBrief.delivery_status}</p>
              {newsBrief.delivery_target ? <p>目標：{newsBrief.delivery_target}</p> : null}
              {newsBrief.delivery_error ? <p className="text-coral">{newsBrief.delivery_error}</p> : null}
            </div>
          </CollapsibleBlock>

          <MarkdownDetails markdown={newsBrief.markdown} />
        </div>
      ) : systemInspection ? (
        <div className="space-y-4">
          <ResultHero
            title={systemInspection.title}
            summary={`升級建議：${systemInspection.version_update_check.upgrade_recommendation}`}
          >
            {onExportMarkdown ? (
              <ActionButton onClick={onExportMarkdown} tone="coral">
                匯出 Markdown
              </ActionButton>
            ) : null}
          </ResultHero>

          <SummaryList title="巡檢總結" items={systemInspection.inspection_summary} />

          <CollapsibleBlock title="高優先級風險">
            <div className="space-y-3">
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
          </CollapsibleBlock>

          <CollapsibleBlock title="建議執行順序">
            <ol className="space-y-1 text-sm leading-6">
              {systemInspection.recommended_execution_order.map((item, index) => (
                <li key={item}>
                  {index + 1}. {item}
                </li>
              ))}
            </ol>
          </CollapsibleBlock>

          <CollapsibleBlock title="版本更新檢查">
            <div className="space-y-2 text-sm leading-6 text-slate-700">
              <p>目前版本：{systemInspection.version_update_check.current_version}</p>
              <p>最新版本：{systemInspection.version_update_check.latest_version ?? "unknown"}</p>
              <ul className="space-y-1">
                {systemInspection.version_update_check.compatibility_risks.map((item) => (
                  <li key={item}>- {item}</li>
                ))}
              </ul>
            </div>
          </CollapsibleBlock>

          <CollapsibleBlock title="修復與交辦">
            <div className="space-y-3 text-sm leading-6 text-slate-700">
              <ul className="space-y-1">
                {systemInspection.fix_and_optimization_actions.map((item) => (
                  <li key={item}>- {item}</li>
                ))}
              </ul>
              {systemInspection.repair_workflow_created ? (
                <div className="pt-2">
                  <p>已自動交辦 Fullstack Engineer Agent。</p>
                  {systemInspection.repair_workflow_run_id ? (
                    <Link
                      href={`/openclaw/development?instanceId=${encodeURIComponent(run?.instance_id ?? "")}&runId=${encodeURIComponent(systemInspection.repair_workflow_run_id)}`}
                      className="font-black text-slate-700 underline decoration-4 underline-offset-4"
                    >
                      Development Workflow：{systemInspection.repair_workflow_run_id}
                    </Link>
                  ) : null}
                </div>
              ) : (
                <p>{systemInspection.repair_workflow_reason ?? "本次巡檢未建立後續工程流程。"}</p>
              )}
              <p>投遞狀態：{systemInspection.delivery_status}</p>
              {systemInspection.delivery_target ? <p>目標：{systemInspection.delivery_target}</p> : null}
              {systemInspection.delivery_error ? <p className="text-coral">{systemInspection.delivery_error}</p> : null}
            </div>
          </CollapsibleBlock>

          <CollapsibleBlock title="Telegram 摘要">
            <pre className="pixel-scrollbar max-h-[220px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
              {systemInspection.telegram_summary}
            </pre>
          </CollapsibleBlock>

          <MarkdownDetails markdown={systemInspection.markdown} />
        </div>
      ) : run?.error_message ? (
        <div className="space-y-4">
          <ResultHero title="執行異常摘要" summary={errorSummary ?? run.error_message}>
            {errorPreview?.title ? <p className="text-xs text-slate-500">標題：{errorPreview.title}</p> : null}
          </ResultHero>

          {errorPreview?.highlights && errorPreview.highlights.length > 0 ? (
            <SummaryList title="重點" items={errorPreview.highlights.slice(0, 3)} />
          ) : null}

          {errorPreview?.artifacts && errorPreview.artifacts.length > 0 ? (
            <SummaryText title="關聯模組" text={errorPreview.artifacts.slice(0, 4).join("、")} />
          ) : null}

          {run.workflow_type === "development_execution" && developmentDelivery ? (
            <CollapsibleBlock title="Discord 匯報">
              <div className="space-y-1 text-sm leading-6 text-slate-700">
                <p>狀態：{developmentDelivery.status}</p>
                {developmentDelivery.target ? <p>目標：{developmentDelivery.target}</p> : null}
                {developmentDelivery.source ? <p>來源：{developmentDelivery.source}</p> : null}
                {developmentDelivery.reason ? <p>說明：{developmentDelivery.reason}</p> : null}
                {developmentDelivery.error ? <p className="text-coral">錯誤：{developmentDelivery.error}</p> : null}
              </div>
            </CollapsibleBlock>
          ) : null}

          <CollapsibleBlock title="查看原始 payload">
            <pre className="pixel-scrollbar max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
              {run.error_message}
            </pre>
          </CollapsibleBlock>
        </div>
      ) : (
        <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
          任務尚未完成。完成後這裡會顯示結果摘要。
        </div>
      )}
    </PixelCard>
  );
}

function ResultHero({
  title,
  summary,
  children
}: {
  title: string;
  summary: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-4 border-ink bg-sand p-4">
      <div className="space-y-2">
        <h3 className="text-lg font-black tracking-[0.08em]">{title}</h3>
        <p className="max-w-4xl text-sm leading-6 text-slate-700">{summary}</p>
      </div>
      {children ? <div className="flex flex-wrap gap-2">{children}</div> : null}
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled = false,
  tone = "ink"
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: "ink" | "coral";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`pixel-button px-4 py-3 text-sm font-black tracking-[0.08em] disabled:opacity-60 ${
        tone === "coral" ? "bg-coral text-white" : "bg-ink text-sand"
      }`}
    >
      {children}
    </button>
  );
}

function SummaryList({ title, items }: { title: string; items: string[] }) {
  return (
    <article className="border-4 border-ink bg-white p-4">
      <h4 className="text-sm font-black tracking-[0.08em]">{title}</h4>
      <ul className="mt-3 space-y-1 text-sm leading-6">
        {items.slice(0, 5).map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </article>
  );
}

function SummaryText({ title, text }: { title: string; text: string }) {
  return (
    <article className="border-4 border-ink bg-white p-4">
      <h4 className="text-sm font-black tracking-[0.08em]">{title}</h4>
      <p className="mt-3 text-sm leading-6 text-slate-700">{text}</p>
    </article>
  );
}

function CollapsibleBlock({
  title,
  children
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <details className="border-4 border-ink bg-white p-4">
      <summary className="cursor-pointer text-sm font-black tracking-[0.08em] text-slate-700">{title}</summary>
      <div className="mt-3">{children}</div>
    </details>
  );
}

function MarkdownDetails({ markdown }: { markdown: string }) {
  return (
    <CollapsibleBlock title="Markdown">
      <pre className="pixel-scrollbar max-h-[420px] overflow-auto bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">
        {markdown}
      </pre>
    </CollapsibleBlock>
  );
}

function SourcePreviewList({
  sources
}: {
  sources: Array<{ key: string; title: string; meta: string; summary: string; note?: string }>;
}) {
  return (
    <div className="space-y-3">
      {sources.map((item) => (
        <div key={item.key} className="border-4 border-ink bg-sand p-3 text-sm">
          <p className="font-black">{item.title}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">{item.meta}</p>
          <p className="mt-2 leading-6">{item.summary}</p>
          {item.note ? <p className="mt-2 text-xs text-slate-500">{item.note}</p> : null}
        </div>
      ))}
    </div>
  );
}

function StoryPreviewSection({
  title,
  stories,
  nested = false
}: {
  title: string;
  stories: Array<{ key: string; title: string; summary: string; note?: string }>;
  nested?: boolean;
}) {
  const content = (
    <div className="space-y-3">
      {stories.slice(0, 3).map((item) => (
        <div key={item.key} className="border-4 border-ink bg-sand p-3 text-sm">
          <p className="font-black">{item.title}</p>
          <p className="mt-2 leading-6">{item.summary}</p>
          {item.note ? <p className="mt-2 text-xs text-slate-500">{item.note}</p> : null}
        </div>
      ))}
    </div>
  );

  if (nested) return content;

  return (
    <article className="border-4 border-ink bg-white p-4">
      <h4 className="text-sm font-black tracking-[0.08em]">{title}</h4>
      <div className="mt-3">{content}</div>
    </article>
  );
}

function workflowContextLabel(run?: WorkflowRunResponse | null) {
  if (!run) return "Agent";
  if (run.workflow_type === "news_brief") return "Daily News Brief agent";
  if (run.workflow_type === "system_inspection") return "System Inspection agent";
  if (run.workflow_type === "development_execution") return "Development agent";
  if (run.workflow_type === "web_search") return "Web Search agent";
  return "Agent";
}

function resolveDevelopmentDelivery(run?: WorkflowRunResponse | null) {
  if (!run || run.workflow_type !== "development_execution") return null;
  if (run.final_development_report) {
    return {
      status: run.final_development_report.delivery_status,
      target: run.final_development_report.delivery_target ?? null,
      error: run.final_development_report.delivery_error ?? null,
      source: run.final_development_report.delivery_source,
      reason: run.final_development_report.delivery_reason ?? null,
    };
  }

  const deliveryEvent = [...run.events].reverse().find((event) => {
    const payload = event.payload;
    return typeof payload.delivery_status === "string";
  });
  if (!deliveryEvent) return null;

  return {
    status: typeof deliveryEvent.payload.delivery_status === "string" ? deliveryEvent.payload.delivery_status : null,
    target: typeof deliveryEvent.payload.delivery_target === "string" ? deliveryEvent.payload.delivery_target : null,
    error: typeof deliveryEvent.payload.delivery_error === "string" ? deliveryEvent.payload.delivery_error : null,
    source: typeof deliveryEvent.payload.delivery_source === "string" ? deliveryEvent.payload.delivery_source : null,
    reason: typeof deliveryEvent.payload.delivery_reason === "string" ? deliveryEvent.payload.delivery_reason : null,
  };
}
