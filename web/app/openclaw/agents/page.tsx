"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import { createOpenClawAgent, fetchOpenClawAgents, fetchOpenClawInstances, updateOpenClawAgentSearchCapability } from "@/lib/api";
import type { OpenClawAgentSummary, OpenClawInstanceResponse } from "@/lib/types";

const AGENT_ROLES = [
  { name: "Chief Lobster", tagline: "Agent 盤點", status: "running", quote: "我會先確認目前是哪個 Instance，再拉出對應的 Agent 清單。" },
  { name: "Agent Steward", tagline: "Agent 建立", status: "ready", quote: "先把名稱、角色提示與 prompt 收斂成穩定的建立表單。" },
  { name: "Binding Scout", tagline: "綁定預留", status: "pending", quote: "Phase 1 先把 Agent 管理骨架做穩，bindings 之後再補深一層。" }
];

export default function OpenClawAgentsPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [agents, setAgents] = useState<OpenClawAgentSummary[]>([]);
  const [name, setName] = useState("Support Agent");
  const [roleHint, setRoleHint] = useState("operator");
  const [prompt, setPrompt] = useState("");
  const [searchEnabledOnCreate, setSearchEnabledOnCreate] = useState(true);
  const [busyCapabilityAgentId, setBusyCapabilityAgentId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  async function loadAgents(instanceId: string) {
    if (!instanceId) {
      setAgents([]);
      return;
    }

    setAgents(await fetchOpenClawAgents(instanceId));
  }

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        const nextInstanceId = instancePayload[0]?.id ?? "";
        setSelectedInstanceId((current) => current || nextInstanceId);
        if (nextInstanceId) {
          await loadAgents(nextInstanceId);
        }
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Agents");
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!selectedInstanceId) {
      return;
    }

    startTransition(async () => {
      try {
        await loadAgents(selectedInstanceId);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 Agent 清單");
      }
    });
  }, [selectedInstanceId, startTransition]);

  async function handleCreateAgent() {
    if (!selectedInstanceId) {
      setError("請先建立 OpenClaw Instance。");
      return;
    }

    setError("");
    setMessage("");

    startTransition(async () => {
      try {
        const agent = await createOpenClawAgent({
          instance_id: selectedInstanceId,
          name,
          prompt: prompt || undefined,
          role_hint: roleHint || undefined
        });
        if (searchEnabledOnCreate) {
          const capability = await updateOpenClawAgentSearchCapability({
            instance_id: selectedInstanceId,
            agent_id: agent.id,
            enabled: true
          });
          setMessage(capability.message || `已建立 Agent：${agent.name}，並啟用原生搜索工具。`);
        } else {
          setMessage(`已建立 Agent：${agent.name}`);
        }
        await loadAgents(selectedInstanceId);
        setPrompt("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 Agent 失敗");
      }
    });
  }

  async function handleToggleSearchCapability(agent: OpenClawAgentSummary, nextEnabled: boolean) {
    if (!selectedInstanceId) {
      setError("請先選擇 OpenClaw Instance。");
      return;
    }

    setBusyCapabilityAgentId(agent.id);
    setError("");
    setMessage("");

    try {
      const capability = await updateOpenClawAgentSearchCapability({
        instance_id: selectedInstanceId,
        agent_id: agent.id,
        enabled: nextEnabled
      });
      await loadAgents(selectedInstanceId);
      setMessage(capability.message || `${agent.name} 原生搜索能力已更新。`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "更新搜索能力失敗");
    } finally {
      setBusyCapabilityAgentId("");
    }
  }

  return (
    <OpenClawPageShell
      title="OpenClaw Agent 管理"
      description="先選擇目標 Instance，再查看目前 Agent 清單或建立新的 Agent。這一版會直接管理原生搜索 plugin readiness，不再依賴 workspace exec 腳本。"
      roles={AGENT_ROLES}
    >
      <PixelCard title="Agent 控制區" eyebrow="Agents">
        <div className="grid gap-4 lg:grid-cols-[280px_auto_auto]">
          <OpenClawInstancePicker
            instances={instances}
            value={selectedInstanceId}
            onChange={setSelectedInstanceId}
          />
          <button
            type="button"
            onClick={() => selectedInstanceId && loadAgents(selectedInstanceId)}
            className="pixel-button bg-teal px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
          >
            重新整理
          </button>
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message || "切換 Instance 後會自動同步 Agent 清單。"}
          </div>
        </div>
      </PixelCard>

      <PixelCard title="建立 Agent" eyebrow="Create">
        <div className="grid gap-4 lg:grid-cols-3">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            placeholder="Agent 名稱"
          />
          <input
            value={roleHint}
            onChange={(event) => setRoleHint(event.target.value)}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            placeholder="role_hint"
          />
          <button
            type="button"
            onClick={handleCreateAgent}
            disabled={isPending}
            className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
          >
            建立 Agent
          </button>
        </div>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          className="mt-4 min-h-[160px] w-full border-4 border-ink bg-sand px-4 py-3 text-sm outline-none"
          placeholder="Agent Prompt（選填）"
        />
        <label className="mt-4 flex items-center gap-3 border-4 border-ink bg-white px-4 py-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={searchEnabledOnCreate}
            onChange={(event) => setSearchEnabledOnCreate(event.target.checked)}
            className="h-4 w-4"
          />
          建立後立刻開啟 `search_api`，並同步原生搜索 plugin
        </label>
      </PixelCard>

      <PixelCard title="Agent 清單" eyebrow="List">
        {instances.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            先到實例頁建立 OpenClaw Instance，這裡才能讀取 Agent 清單。
          </div>
        ) : agents.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            {isPending ? "正在同步 Agent 清單..." : "目前沒有 Agent，請先建立第一個 Agent。"}
          </div>
        ) : (
          <div className="space-y-3">
            {agents.map((agent) => (
              <article key={agent.id} className="border-4 border-ink bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-black tracking-[0.08em]">{agent.name}</h3>
                    <p className="mt-1 text-xs text-slate-500">{agent.id}</p>
                  </div>
                  <StatusPill status={agent.status} />
                </div>
                <div className="mt-3 text-sm text-slate-700">綁定通道數：{agent.channel_count}</div>
                <div className="mt-3 border-4 border-ink bg-sand p-3 text-sm text-slate-700">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      搜索能力：
                      <span className="ml-2 font-black">
                        {isSearchCapabilityEnabled(agent) ? "已啟用" : "未啟用"}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleToggleSearchCapability(agent, !isSearchCapabilityEnabled(agent))}
                      disabled={busyCapabilityAgentId === agent.id}
                      className="pixel-button bg-coral px-4 py-2 text-xs font-black tracking-[0.08em] text-white disabled:opacity-60"
                    >
                      {busyCapabilityAgentId === agent.id
                        ? "同步中..."
                        : isSearchCapabilityEnabled(agent)
                          ? "停用搜索能力"
                          : "啟用搜索能力"}
                    </button>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs lg:grid-cols-3">
                    <div className="border-4 border-ink bg-white px-3 py-2">
                      <span className="font-black">Native Plugin</span>
                      <div className="mt-1">
                        {getSearchCapabilityFlag(agent, "plugin_ready") ? "已就緒" : "未就緒"}
                      </div>
                    </div>
                    <div className="border-4 border-ink bg-white px-3 py-2">
                      <span className="font-black">Plugin 啟用</span>
                      <div className="mt-1">
                        {getSearchCapabilityFlag(agent, "plugin_enabled") ? "已啟用" : "未啟用"}
                      </div>
                    </div>
                    <div className="border-4 border-ink bg-white px-3 py-2">
                      <span className="font-black">ACPX Bridge</span>
                      <div className="mt-1">
                        {getSearchCapabilityFlag(agent, "bridge_ready") ? "已就緒" : "待處理"}
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 text-xs text-slate-500">
                    {getSearchCapabilityMessage(agent) || "啟用後會把 repo 內原生 plugin 掛到 OpenClaw，之後 agent 會直接呼叫 native tool。"}
                  </div>
                  {getSearchCapabilityPluginId(agent) ? (
                    <div className="mt-1 text-[11px] uppercase tracking-[0.08em] text-slate-400">
                      plugin id: {getSearchCapabilityPluginId(agent)}
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </PixelCard>
    </OpenClawPageShell>
  );
}

function isSearchCapabilityEnabled(agent: OpenClawAgentSummary): boolean {
  const capabilities = agent.metadata.capabilities;
  if (!capabilities || typeof capabilities !== "object") {
    return false;
  }

  const searchCapability = (capabilities as Record<string, unknown>).search_api;
  if (!searchCapability || typeof searchCapability !== "object") {
    return false;
  }

  return Boolean((searchCapability as Record<string, unknown>).enabled);
}

function getSearchCapabilityFlag(agent: OpenClawAgentSummary, key: string): boolean {
  const capability = getSearchCapability(agent);
  return Boolean(capability?.[key]);
}

function getSearchCapabilityMessage(agent: OpenClawAgentSummary): string {
  const capability = getSearchCapability(agent);
  const value = capability?.last_sync_message;
  return typeof value === "string" ? value : "";
}

function getSearchCapabilityPluginId(agent: OpenClawAgentSummary): string {
  const capability = getSearchCapability(agent);
  const value = capability?.plugin_id;
  return typeof value === "string" ? value : "";
}

function getSearchCapability(agent: OpenClawAgentSummary): Record<string, unknown> | null {
  const capabilities = agent.metadata.capabilities;
  if (!capabilities || typeof capabilities !== "object") {
    return null;
  }

  const searchCapability = (capabilities as Record<string, unknown>).search_api;
  if (!searchCapability || typeof searchCapability !== "object") {
    return null;
  }

  return searchCapability as Record<string, unknown>;
}
