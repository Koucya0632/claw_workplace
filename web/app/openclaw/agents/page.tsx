"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import { createOpenClawAgent, fetchOpenClawAgents, fetchOpenClawInstances } from "@/lib/api";
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
        await loadAgents(selectedInstanceId);
        setPrompt("");
        setMessage(`已建立 Agent：${agent.name}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 Agent 失敗");
      }
    });
  }

  return (
    <OpenClawPageShell
      title="OpenClaw Agent 管理"
      description="先選擇目標 Instance，再查看目前 Agent 清單或建立新的 Agent。Phase 1 先聚焦於清單與建立流程。"
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
              </article>
            ))}
          </div>
        )}
      </PixelCard>
    </OpenClawPageShell>
  );
}
