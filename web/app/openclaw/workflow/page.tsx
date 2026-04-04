"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { fetchOpenClawAgents, fetchOpenClawInstances, fetchOpenClawWorkflowConfig, updateOpenClawWorkflowConfig } from "@/lib/api";
import type { OpenClawAgentSummary, OpenClawInstanceResponse } from "@/lib/types";

const WORKFLOW_ROLES = [
  { name: "Chief Lobster", tagline: "流程編排", status: "running", quote: "我會先確認這個 Instance 的三階段 agent 是否都已就緒。" },
  { name: "Search Lobster", tagline: "搜索代理", status: "ready", quote: "先指定誰負責搜索，前台工作流才知道第一步交給誰。" },
  { name: "Analyze Lobster", tagline: "分析代理", status: "ready", quote: "分析 agent 會讀取搜索輸出，再整理重點與風險。" },
  { name: "Report Lobster", tagline: "報告代理", status: "ready", quote: "最後一棒負責把分析結果轉成結構化報告與 Markdown。" }
];

export default function OpenClawWorkflowPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [agents, setAgents] = useState<OpenClawAgentSummary[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [searchAgentId, setSearchAgentId] = useState("");
  const [analysisAgentId, setAnalysisAgentId] = useState("");
  const [reportAgentId, setReportAgentId] = useState("");
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
          setSearchAgentId(configPayload.value.search_agent_id);
          setAnalysisAgentId(configPayload.value.analysis_agent_id);
          setReportAgentId(configPayload.value.report_agent_id);
          setMessage("已載入目前 workflow agent mapping。");
        } else {
          setSearchAgentId("");
          setAnalysisAgentId("");
          setReportAgentId("");
          setMessage("此 Instance 尚未設定 workflow agent mapping。");
        }
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 workflow 設定");
      }
    });
  }, [selectedInstanceId, startTransition]);

  async function handleSave() {
    if (!selectedInstanceId || !searchAgentId || !analysisAgentId || !reportAgentId) {
      setError("請完整指定搜索、分析、報告三個 agent。");
      return;
    }

    setError("");
    setMessage("");
    startTransition(async () => {
      try {
        const payload = await updateOpenClawWorkflowConfig({
          instance_id: selectedInstanceId,
          search_agent_id: searchAgentId,
          analysis_agent_id: analysisAgentId,
          report_agent_id: reportAgentId
        });
        setMessage(`workflow agent mapping 已更新：${payload.search_agent_id} / ${payload.analysis_agent_id} / ${payload.report_agent_id}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "儲存 workflow 設定失敗");
      }
    });
  }

  return (
    <OpenClawPageShell
      title="Workflow Agent Mapping"
      description="這裡決定一體化流程的三個固定階段要交給哪個 OpenClaw agent。先配置好 mapping，`/search` 的工作流主頁才能真正串起搜索、分析、報告。"
      roles={WORKFLOW_ROLES}
    >
      <PixelCard title="Workflow 設定" eyebrow="Mapping">
        <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <OpenClawInstancePicker instances={instances} value={selectedInstanceId} onChange={setSelectedInstanceId} />
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message || "先選擇 Instance，再為三個 stage 指定 agent。"}
          </div>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <StageAgentSelector label="搜索 Agent" value={searchAgentId} onChange={setSearchAgentId} agents={agents} />
          <StageAgentSelector label="分析 Agent" value={analysisAgentId} onChange={setAnalysisAgentId} agents={agents} />
          <StageAgentSelector label="報告 Agent" value={reportAgentId} onChange={setReportAgentId} agents={agents} />
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
  // stage selector 讓三個固定階段都用同一種選單樣式，避免管理頁視覺漂移。
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
