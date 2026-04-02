"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { dispatchOpenClawAgentHook, dispatchOpenClawWakeHook, fetchOpenClawInstances } from "@/lib/api";
import type { OpenClawInstanceResponse } from "@/lib/types";

const ACTION_ROLES = [
  { name: "Chief Lobster", tagline: "手動派發", status: "running", quote: "我會先確認 instance / agent / sessionKey，再把任務送進 OpenClaw agent turn。" },
  { name: "Hook Runner", tagline: "Agent Hook", status: "ready", quote: "這張表單現在會透過 `openclaw agent` 測試指定 Agent 是否能接住任務。" },
  { name: "Wake Signal", tagline: "Wake Hook", status: "disabled", quote: "目前這個 OpenClaw 版本沒有穩定可用的 wake 派發入口，先保留為提示區。" }
];

type AgentHookResult = {
  runId?: string;
  status?: string;
  summary?: string;
  result?: {
    payloads?: Array<{
      text?: string | null;
    }>;
    meta?: {
      durationMs?: number;
    };
  };
};

export default function OpenClawActionsPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [agentId, setAgentId] = useState("support-agent");
  const [sessionKey, setSessionKey] = useState("ticket-1001");
  const [messageText, setMessageText] = useState("請整理這筆客服訊息並草擬回應。");
  const [channel, setChannel] = useState("");
  const [to, setTo] = useState("");
  const [metadataText, setMetadataText] = useState("{\n  \"priority\": \"high\"\n}");
  const [wakeAgentId, setWakeAgentId] = useState("support-agent");
  const [wakeSessionKey, setWakeSessionKey] = useState("ticket-1001");
  const [wakeChannel, setWakeChannel] = useState("");
  const [wakeTo, setWakeTo] = useState("");
  const [wakeMetadataText, setWakeMetadataText] = useState("{\n  \"source\": \"manual\"\n}");
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [agentResult, setAgentResult] = useState<AgentHookResult | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        setSelectedInstanceId(instancePayload[0]?.id ?? "");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Actions");
      }
    });
  }, [startTransition]);

  function parseMetadata(input: string) {
    return input.trim() ? (JSON.parse(input) as Record<string, unknown>) : {};
  }

  async function handleAgentHook() {
    setBusyAction("agent");
    setError("");
    setMessage("");
    setAgentResult(null);

    try {
      const result = await dispatchOpenClawAgentHook({
        instance_id: selectedInstanceId,
        agent_id: agentId,
        session_key: sessionKey,
        message: messageText,
        channel: channel || undefined,
        to: to || undefined,
        metadata: parseMetadata(metadataText)
      });
      setAgentResult((result ?? {}) as AgentHookResult);
      setMessage("Agent Hook 派發完成");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Agent Hook 派發失敗");
    } finally {
      setBusyAction("");
    }
  }

  async function handleWakeHook() {
    setBusyAction("wake");
    setError("");
    setMessage("");
    setAgentResult(null);

    try {
      const result = await dispatchOpenClawWakeHook({
        instance_id: selectedInstanceId,
        agent_id: wakeAgentId,
        session_key: wakeSessionKey,
        channel: wakeChannel || undefined,
        to: wakeTo || undefined,
        metadata: parseMetadata(wakeMetadataText)
      });
      setMessage(`Wake Hook 派發完成：${JSON.stringify(result)}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Wake Hook 派發失敗");
    } finally {
      setBusyAction("");
    }
  }

  return (
    <OpenClawPageShell
      title="OpenClaw Actions"
      description="Actions 頁目前以 `openclaw agent` CLI 模擬手動派發。Agent Hook 可直接測試 agent turn；Wake Hook 在這個 OpenClaw 版本暫不支援。"
      roles={ACTION_ROLES}
    >
      <PixelCard title="共用派發上下文" eyebrow="Context">
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <OpenClawInstancePicker
            instances={instances}
            value={selectedInstanceId}
            onChange={setSelectedInstanceId}
          />
          <div className="grid gap-4">
            <div className="border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
              {error ? <span className="text-coral">{error}</span> : message || "metadata 需輸入合法 JSON，送出前會先在前端解析。"}
            </div>
            {agentResult ? (
              <div className="grid gap-3 border-4 border-ink bg-sand p-4 text-sm text-slate-800">
                <div className="flex flex-wrap gap-2">
                  <span className="border-2 border-ink bg-leaf px-3 py-1 text-xs font-black uppercase tracking-[0.08em] text-white">
                    {agentResult.status || "ok"}
                  </span>
                  {agentResult.summary ? (
                    <span className="border-2 border-ink bg-white px-3 py-1 text-xs font-black uppercase tracking-[0.08em] text-slate-700">
                      {agentResult.summary}
                    </span>
                  ) : null}
                </div>
                {agentResult.runId ? (
                  <p className="text-xs leading-6 text-slate-600">Run ID: {agentResult.runId}</p>
                ) : null}
                {typeof agentResult.result?.meta?.durationMs === "number" ? (
                  <p className="text-xs leading-6 text-slate-600">
                    執行時間：約 {(agentResult.result.meta.durationMs / 1000).toFixed(1)} 秒
                  </p>
                ) : null}
                <div className="border-4 border-ink bg-white p-4">
                  <p className="mb-2 text-xs font-black uppercase tracking-[0.08em] text-slate-500">Agent Reply</p>
                  <p className="whitespace-pre-wrap leading-7 text-slate-800">
                    {agentResult.result?.payloads?.[0]?.text || "這次執行沒有回傳文字內容。"}
                  </p>
                </div>
                <details className="border-4 border-ink bg-white p-4">
                  <summary className="cursor-pointer text-xs font-black uppercase tracking-[0.08em] text-slate-600">
                    查看原始回應 JSON
                  </summary>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all bg-slate-950/95 p-4 font-mono text-xs leading-6 text-slate-100">
                    {JSON.stringify(agentResult, null, 2)}
                  </pre>
                </details>
              </div>
            ) : null}
          </div>
        </div>
      </PixelCard>

      <div className="grid gap-5 xl:grid-cols-2">
        <PixelCard title="CLI Agent Dispatch" eyebrow="Agent Hook">
          <div className="grid gap-4">
            <input
              value={agentId}
              onChange={(event) => setAgentId(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="agent_id"
            />
            <input
              value={sessionKey}
              onChange={(event) => setSessionKey(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="session_key"
            />
            <input
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="channel"
            />
            <input
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="to（選填）"
            />
            <textarea
              value={messageText}
              onChange={(event) => setMessageText(event.target.value)}
              className="min-h-[120px] border-4 border-ink bg-sand px-4 py-3 text-sm outline-none"
              placeholder="message"
            />
            <textarea
              value={metadataText}
              onChange={(event) => setMetadataText(event.target.value)}
              className="min-h-[140px] border-4 border-ink bg-sand px-4 py-3 font-mono text-sm outline-none"
              placeholder="metadata JSON"
            />
            <button
              type="button"
              onClick={handleAgentHook}
              disabled={busyAction === "agent" || !selectedInstanceId}
              className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
            >
              {busyAction === "agent" ? "派發中..." : "送出 Agent Hook"}
            </button>
          </div>
        </PixelCard>

        <PixelCard title="Wake Hook 暫不支援" eyebrow="Wake Hook">
          <div className="grid gap-4">
            <input
              value={wakeAgentId}
              onChange={(event) => setWakeAgentId(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="agent_id"
            />
            <input
              value={wakeSessionKey}
              onChange={(event) => setWakeSessionKey(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="session_key"
            />
            <input
              value={wakeChannel}
              onChange={(event) => setWakeChannel(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="channel"
            />
            <input
              value={wakeTo}
              onChange={(event) => setWakeTo(event.target.value)}
              className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
              placeholder="to（選填）"
            />
            <textarea
              value={wakeMetadataText}
              onChange={(event) => setWakeMetadataText(event.target.value)}
              className="min-h-[140px] border-4 border-ink bg-sand px-4 py-3 font-mono text-sm outline-none"
              placeholder="metadata JSON"
            />
            <button
              type="button"
              onClick={handleWakeHook}
              disabled
              className="pixel-button bg-slate-300 px-4 py-3 text-sm font-black tracking-[0.08em] text-slate-600 disabled:opacity-80"
            >
              Wake Hook 目前未開放
            </button>
            <div className="border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
              目前這個 OpenClaw 版本沒有穩定可用的 wake 派發入口。若要測試任務派發，請先使用左側的 Agent Hook。
            </div>
          </div>
        </PixelCard>
      </div>
    </OpenClawPageShell>
  );
}
