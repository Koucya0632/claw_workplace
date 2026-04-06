"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import {
  fetchOpenClawAgents,
  fetchOpenClawInstances,
  fetchOpenClawWorkflowConfig,
  updateOpenClawWorkflowConfig
} from "@/lib/api";
import type {
  OpenClawAgentSummary,
  OpenClawInstanceResponse,
  OpenClawWorkflowHandoffPolicy,
  OpenClawWorkflowRoutingRule,
  OpenClawWorkflowSpecialistAgents
} from "@/lib/types";

const WORKFLOW_ROLES = [
  { name: "Secretary Controller", tagline: "主控秘書", status: "running", quote: "我會接手需求、拆分任務、分派專職 agent、整合結果，並在異常時決定是否人工接管。" },
  { name: "Core Specialists", tagline: "核心流程", status: "ready", quote: "搜索、分析、報告三槽會維持主流程穩定運作，避免既有 `/search` workflow 失效。" },
  { name: "Extended Specialists", tagline: "專職池", status: "ready", quote: "Web 搜索、整理、寫作、全端工程、測試設計、UI 檢查、流程監控都能各自映射到獨立 agent。" },
  { name: "Policy Layer", tagline: "分派 / 接管規則", status: "ready", quote: "routing rules 與 handoff policy 會定義何時派工、何時降級、何時升級人工處理。" }
];

const DEFAULT_ROUTING_RULES: OpenClawWorkflowRoutingRule[] = [
  {
    key: "prefer-web-search",
    label: "網址 / 網域 / 網站條件優先派 Web 搜索代理",
    enabled: true,
    conditions: ["url", "domain", "site"],
    route_to: ["search_web"]
  },
  {
    key: "prefer-project-search",
    label: "source_id / 文件 / 內部知識庫條件優先派搜索代理",
    enabled: true,
    conditions: ["source_id", "document", "knowledge-base"],
    route_to: ["search_agent_id"]
  },
  {
    key: "analysis-required",
    label: "比較 / 差異 / 風險 / 建議關鍵詞必派分析代理",
    enabled: true,
    conditions: ["比較", "差異", "風險", "建議"],
    route_to: ["analysis_agent_id"]
  },
  {
    key: "writer-required",
    label: "報告 / 對外回覆 / markdown 關鍵詞必派寫作代理",
    enabled: true,
    conditions: ["報告", "回覆", "markdown"],
    route_to: ["writer", "report_agent_id"]
  }
];

const DEFAULT_HANDOFF_POLICY: OpenClawWorkflowHandoffPolicy = {
  manual_review_required_on_conflict: true,
  manual_review_required_on_high_risk: true,
  max_search_retry_count: 1,
  max_report_retry_count: 2,
  timeout_escalation_seconds: 180,
  fallback_mode: "controller"
};

const DEFAULT_SPECIALISTS: OpenClawWorkflowSpecialistAgents = {
  search_web: { agent_id: "", enabled: false },
  organizer: { agent_id: "", enabled: false },
  writer: { agent_id: "", enabled: false },
  test_design: { agent_id: "", enabled: false },
  ui_review: { agent_id: "", enabled: false },
  monitor: { agent_id: "", enabled: false },
  fullstack_engineer: { agent_id: "", enabled: false },
  daily_news_brief: { agent_id: "", enabled: false },
  system_inspection: { agent_id: "", enabled: false }
};

const SPECIALIST_FIELDS: Array<{ key: keyof OpenClawWorkflowSpecialistAgents; label: string; description: string }> = [
  { key: "search_web", label: "Web 搜索代理", description: "外部網站 / 網域條件搜尋" },
  { key: "organizer", label: "整理代理", description: "去重、分類、結構化整理" },
  { key: "writer", label: "寫作代理", description: "正式報告、回覆稿、對外交付" },
  { key: "fullstack_engineer", label: "Fullstack Engineer Agent", description: "工程任務唯一執行入口，負責分析、設計、排期、開發、測試與匯報" },
  { key: "test_design", label: "測試設計代理", description: "測試案例、驗收條件、驗證清單" },
  { key: "ui_review", label: "UI 檢查代理", description: "UI 文案、流程清晰度、交互檢查" },
  { key: "monitor", label: "流程監控代理", description: "超時、失敗、重試與人工接管提示" },
  { key: "daily_news_brief", label: "Daily News Brief Agent", description: "每日新聞監控、去重、排序、摘要與投遞" },
  { key: "system_inspection", label: "System Inspection Agent", description: "版本更新巡檢、日誌分析、風險評估與修復建議" }
];

export default function OpenClawWorkflowPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [agents, setAgents] = useState<OpenClawAgentSummary[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [controllerAgentId, setControllerAgentId] = useState("");
  const [searchAgentId, setSearchAgentId] = useState("");
  const [analysisAgentId, setAnalysisAgentId] = useState("");
  const [reportAgentId, setReportAgentId] = useState("");
  const [specialists, setSpecialists] = useState<OpenClawWorkflowSpecialistAgents>(DEFAULT_SPECIALISTS);
  const [routingRulesText, setRoutingRulesText] = useState(JSON.stringify(DEFAULT_ROUTING_RULES, null, 2));
  const [handoffPolicyText, setHandoffPolicyText] = useState(JSON.stringify(DEFAULT_HANDOFF_POLICY, null, 2));
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        const nextInstanceId = instancePayload[0]?.id ?? "";
        setSelectedInstanceId((current) => current || nextInstanceId);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Instances");
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!selectedInstanceId) {
      setAgents([]);
      return;
    }

    startTransition(async () => {
      try {
        const [agentPayload, configPayload] = await Promise.allSettled([
          fetchOpenClawAgents(selectedInstanceId),
          fetchOpenClawWorkflowConfig(selectedInstanceId)
        ]);

        if (agentPayload.status === "fulfilled") {
          setAgents(agentPayload.value);
        } else {
          throw agentPayload.reason;
        }

        if (configPayload.status === "fulfilled") {
          setControllerAgentId(configPayload.value.controller_agent_id);
          setSearchAgentId(configPayload.value.search_agent_id);
          setAnalysisAgentId(configPayload.value.analysis_agent_id);
          setReportAgentId(configPayload.value.report_agent_id);
          setSpecialists(configPayload.value.specialist_agents);
          setRoutingRulesText(JSON.stringify(configPayload.value.routing_rules, null, 2));
          setHandoffPolicyText(JSON.stringify(configPayload.value.handoff_policy, null, 2));
          setMessage("已載入主控秘書與多專職 agent mapping。");
        } else {
          const fallbackController = "main";
          setControllerAgentId(fallbackController);
          setSearchAgentId("");
          setAnalysisAgentId("");
          setReportAgentId("");
          setSpecialists(DEFAULT_SPECIALISTS);
          setRoutingRulesText(JSON.stringify(DEFAULT_ROUTING_RULES, null, 2));
          setHandoffPolicyText(JSON.stringify(DEFAULT_HANDOFF_POLICY, null, 2));
          setMessage("此 Instance 尚未設定進階 workflow mapping，已帶入推薦預設值。");
        }
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 workflow 設定");
      }
    });
  }, [selectedInstanceId, startTransition]);

  async function handleSave() {
    if (!selectedInstanceId || !controllerAgentId || !searchAgentId || !analysisAgentId || !reportAgentId) {
      setError("請完整指定主控秘書與核心搜索 / 分析 / 報告 agent。");
      return;
    }

    let parsedRoutingRules: OpenClawWorkflowRoutingRule[];
    let parsedHandoffPolicy: OpenClawWorkflowHandoffPolicy;
    try {
      parsedRoutingRules = JSON.parse(routingRulesText) as OpenClawWorkflowRoutingRule[];
      parsedHandoffPolicy = JSON.parse(handoffPolicyText) as OpenClawWorkflowHandoffPolicy;
    } catch (parseError) {
      setError(parseError instanceof Error ? `規則 JSON 解析失敗：${parseError.message}` : "規則 JSON 解析失敗");
      return;
    }

    setError("");
    setMessage("");
    startTransition(async () => {
      try {
        const payload = await updateOpenClawWorkflowConfig({
          instance_id: selectedInstanceId,
          controller_agent_id: controllerAgentId,
          search_agent_id: searchAgentId,
          analysis_agent_id: analysisAgentId,
          report_agent_id: reportAgentId,
          specialist_agents: specialists,
          routing_rules: parsedRoutingRules,
          handoff_policy: parsedHandoffPolicy
        });
        setMessage(
          `mapping 已更新：主控秘書 ${payload.controller_agent_id}；核心流程 ${payload.search_agent_id} / ${payload.analysis_agent_id} / ${payload.report_agent_id}`
        );
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "儲存 workflow 設定失敗");
      }
    });
  }

  return (
    <OpenClawPageShell
      title="Workflow Agent Mapping"
      description="這裡決定主控秘書 agent、核心流程 agent、專職池與分派 / 接管規則。配置完成後，`/search` 的 workflow 與 Web Search 都會按這套協作邏輯運作。"
      roles={WORKFLOW_ROLES}
    >
      <PixelCard title="Workflow 設定" eyebrow="Mapping">
        <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm leading-7 text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message || "先選擇 Instance，再配置主控秘書與多專職 agent。"}
          </div>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-4">
          <StageAgentSelector label="主控秘書 Agent" value={controllerAgentId} onChange={setControllerAgentId} agents={agents} />
          <StageAgentSelector label="搜索 Agent" value={searchAgentId} onChange={setSearchAgentId} agents={agents} />
          <StageAgentSelector label="分析 Agent" value={analysisAgentId} onChange={setAnalysisAgentId} agents={agents} />
          <StageAgentSelector label="報告 Agent" value={reportAgentId} onChange={setReportAgentId} agents={agents} />
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          {SPECIALIST_FIELDS.map((field) => (
            <SpecialistAgentCard
              key={field.key}
              label={field.label}
              description={field.description}
              binding={specialists[field.key]}
              agents={agents}
              onChange={(nextBinding) =>
                setSpecialists((current) => ({
                  ...current,
                  [field.key]: nextBinding
                }))
              }
            />
          ))}
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <JsonEditorCard
            title="Routing Rules"
            description="主控秘書會依這些規則決定要派給哪類專職 agent。"
            value={routingRulesText}
            onChange={setRoutingRulesText}
          />
          <JsonEditorCard
            title="Handoff Policy"
            description="定義重試次數、超時升級與人工接管條件。"
            value={handoffPolicyText}
            onChange={setHandoffPolicyText}
          />
        </div>

        <button
          type="button"
          onClick={handleSave}
          disabled={isPending}
          className="pixel-button mt-4 bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
        >
          {isPending ? "儲存中..." : "儲存 Workflow 設定"}
        </button>
      </PixelCard>
    </OpenClawPageShell>
  );
}

interface StageAgentSelectorProps {
  label: string;
  value: string;
  onChange: (nextValue: string) => void;
  agents: OpenClawAgentSummary[];
}

function StageAgentSelector({ label, value, onChange, agents }: StageAgentSelectorProps) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-black tracking-[0.08em]">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
      >
        <option value="">請選擇 Agent</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name} ({agent.id})
          </option>
        ))}
      </select>
    </label>
  );
}

function SpecialistAgentCard({
  label,
  description,
  binding,
  agents,
  onChange
}: {
  label: string;
  description: string;
  binding: { agent_id: string; enabled: boolean };
  agents: OpenClawAgentSummary[];
  onChange: (nextBinding: { agent_id: string; enabled: boolean }) => void;
}) {
  return (
    <div className="border-4 border-ink bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-black tracking-[0.08em]">{label}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
        </div>
        <label className="flex items-center gap-2 text-xs font-black tracking-[0.08em]">
          <input
            type="checkbox"
            checked={binding.enabled}
            onChange={(event) =>
              onChange({
                ...binding,
                enabled: event.target.checked
              })
            }
          />
          啟用
        </label>
      </div>
      <select
        value={binding.agent_id}
        onChange={(event) =>
          onChange({
            ...binding,
            agent_id: event.target.value
          })
        }
        className="mt-4 w-full border-4 border-ink bg-sand px-4 py-3 text-sm outline-none"
      >
        <option value="">請選擇 Agent</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name} ({agent.id})
          </option>
        ))}
      </select>
    </div>
  );
}

function JsonEditorCard({
  title,
  description,
  value,
  onChange
}: {
  title: string;
  description: string;
  value: string;
  onChange: (nextValue: string) => void;
}) {
  return (
    <div className="border-4 border-ink bg-white p-4">
      <h3 className="text-sm font-black tracking-[0.08em]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={14}
        className="pixel-scrollbar mt-4 w-full border-4 border-ink bg-sand px-4 py-3 font-mono text-xs leading-6 outline-none"
      />
    </div>
  );
}
