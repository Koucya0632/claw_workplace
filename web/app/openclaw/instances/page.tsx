"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import { createOpenClawInstance, fetchOpenClawHealth, fetchOpenClawInstances, updateOpenClawInstance } from "@/lib/api";
import type { OpenClawInstanceResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const INSTANCE_ROLES = [
  { name: "Chief Lobster", tagline: "實例註冊", status: "running", quote: "我會先把 Gateway 入口與 token 收斂到安全的後端保存。 " },
  { name: "Gateway Keeper", tagline: "健康巡檢", status: "ready", quote: "每次健康檢查都會寫回最近狀態，方便總覽頁快速判斷。" },
  { name: "Token Guard", tagline: "密鑰封裝", status: "ready", quote: "token 只允許輸入，不會在畫面中回顯。" },
  { name: "Ops Recorder", tagline: "審計追蹤", status: "pending", quote: "建立與更新 Instance 後，操作紀錄會同步寫入審計表。" }
];

interface InstanceDraft {
  name: string;
  gateway_url: string;
  token: string;
  clear_token: boolean;
  is_active: boolean;
}

export default function OpenClawInstancesPage() {
  // 實例頁需要同時處理新增、編輯與健康檢查，因此保留獨立的草稿狀態。
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [drafts, setDrafts] = useState<Record<string, InstanceDraft>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [name, setName] = useState("Primary Gateway");
  const [gatewayUrl, setGatewayUrl] = useState("http://localhost:8080");
  const [token, setToken] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [busySaveId, setBusySaveId] = useState<string | null>(null);
  const [busyHealthId, setBusyHealthId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function loadInstances() {
    const payload = await fetchOpenClawInstances();
    setInstances(payload);
    setDrafts((previous) =>
      Object.fromEntries(
        payload.map((instance) => [
          instance.id,
          {
            name: previous[instance.id]?.name ?? instance.name,
            gateway_url: previous[instance.id]?.gateway_url ?? instance.gateway_url,
            token: "",
            clear_token: false,
            is_active: previous[instance.id]?.is_active ?? instance.is_active
          }
        ])
      )
    );
  }

  useEffect(() => {
    startTransition(async () => {
      setIsLoading(true);
      try {
        await loadInstances();
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 OpenClaw Instance");
      } finally {
        setIsLoading(false);
      }
    });
  }, [startTransition]);

  async function handleCreateInstance() {
    setError("");
    setMessage("");

    startTransition(async () => {
      try {
        const instance = await createOpenClawInstance({
          name,
          gateway_url: gatewayUrl,
          token: token || undefined,
          is_active: isActive
        });
        await loadInstances();
        setToken("");
        setMessage(`已建立 OpenClaw Instance：${instance.name}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "建立 Instance 失敗");
      }
    });
  }

  async function handleSaveInstance(instanceId: string) {
    const draft = drafts[instanceId];
    if (!draft) {
      return;
    }

    setBusySaveId(instanceId);
    setError("");
    setMessage("");

    try {
      await updateOpenClawInstance(instanceId, {
        name: draft.name,
        gateway_url: draft.gateway_url,
        token: draft.token || undefined,
        clear_token: draft.clear_token,
        is_active: draft.is_active
      });
      await loadInstances();
      setMessage("Instance 設定已更新。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "更新 Instance 失敗");
    } finally {
      setBusySaveId(null);
    }
  }

  async function handleHealthCheck(instanceId: string) {
    setBusyHealthId(instanceId);
    setError("");
    setMessage("");

    try {
      const result = await fetchOpenClawHealth(instanceId);
      await loadInstances();
      setMessage(`健康檢查完成：${result.status}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "健康檢查失敗");
    } finally {
      setBusyHealthId(null);
    }
  }

  function updateDraft(instanceId: string, nextDraft: Partial<InstanceDraft>) {
    setDrafts((previous) => ({
      ...previous,
      [instanceId]: {
        ...previous[instanceId],
        ...nextDraft
      }
    }));
  }

  return (
    <OpenClawPageShell
      title="OpenClaw Instance 管理"
      description="這一頁負責新增、編輯與巡檢 OpenClaw Instance。Gateway token 只會送往後端保存，不會在畫面中重新顯示。"
      roles={INSTANCE_ROLES}
    >
      <PixelCard title="新增 Instance" eyebrow="Create">
        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr_1fr_auto]">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            placeholder="Instance 名稱"
          />
          <input
            value={gatewayUrl}
            onChange={(event) => setGatewayUrl(event.target.value)}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            placeholder="Gateway URL"
          />
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            placeholder="Gateway Token"
            type="password"
          />
          <button
            type="button"
            onClick={handleCreateInstance}
            disabled={isPending}
            className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
          >
            建立 Instance
          </button>
        </div>
        <label className="mt-4 inline-flex items-center gap-3 text-sm text-slate-700">
          <input checked={isActive} onChange={(event) => setIsActive(event.target.checked)} type="checkbox" />
          建立後立即啟用
        </label>
        <div className="mt-4 border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
          {error ? <span className="text-coral">{error}</span> : message || "若要保存 token，請先設定 OPENCLAW_SECRET_KEY。"}
        </div>
      </PixelCard>

      <PixelCard title="現有 Instance" eyebrow="Registry">
        {isLoading ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            正在同步 OpenClaw Instance...
          </div>
        ) : instances.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            {isPending ? "正在整理最新畫面..." : "尚未建立任何 OpenClaw Instance。"}
          </div>
        ) : (
          <div className="space-y-4">
            {instances.map((instance) => {
              const draft = drafts[instance.id];

              return (
                <article key={instance.id} className="border-4 border-ink bg-white p-4">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-black tracking-[0.08em]">{instance.name}</h3>
                      <p className="mt-1 text-xs text-slate-500">{instance.id}</p>
                    </div>
                    <StatusPill status={instance.last_health_status ?? "pending"} />
                  </div>

                  <div className="grid gap-3 lg:grid-cols-2">
                    <input
                      value={draft?.name ?? ""}
                      onChange={(event) => updateDraft(instance.id, { name: event.target.value })}
                      className="border-4 border-ink bg-sand px-4 py-3 text-sm outline-none"
                    />
                    <input
                      value={draft?.gateway_url ?? ""}
                      onChange={(event) => updateDraft(instance.id, { gateway_url: event.target.value })}
                      className="border-4 border-ink bg-sand px-4 py-3 text-sm outline-none"
                    />
                    <input
                      value={draft?.token ?? ""}
                      onChange={(event) => updateDraft(instance.id, { token: event.target.value })}
                      className="border-4 border-ink bg-sand px-4 py-3 text-sm outline-none"
                      placeholder={instance.has_token ? "已有 token，輸入新值可覆蓋" : "尚未保存 token"}
                      type="password"
                    />
                    <div className="flex flex-wrap items-center gap-4 border-4 border-ink bg-sand px-4 py-3 text-sm text-slate-700">
                      <label className="inline-flex items-center gap-2">
                        <input
                          checked={draft?.is_active ?? false}
                          onChange={(event) => updateDraft(instance.id, { is_active: event.target.checked })}
                          type="checkbox"
                        />
                        啟用
                      </label>
                      <label className="inline-flex items-center gap-2">
                        <input
                          checked={draft?.clear_token ?? false}
                          onChange={(event) => updateDraft(instance.id, { clear_token: event.target.checked })}
                          type="checkbox"
                        />
                        清除既有 token
                      </label>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
                    <span>最近巡檢：{formatDateTime(instance.last_health_checked_at)}</span>
                    <span>{instance.has_token ? "後端已保存 token" : "目前未保存 token"}</span>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => handleSaveInstance(instance.id)}
                      disabled={busySaveId === instance.id}
                      className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60"
                    >
                      {busySaveId === instance.id ? "保存中..." : "保存設定"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleHealthCheck(instance.id)}
                      disabled={busyHealthId === instance.id}
                      className="pixel-button bg-teal px-4 py-3 text-sm font-black tracking-[0.08em] text-white disabled:opacity-60"
                    >
                      {busyHealthId === instance.id ? "巡檢中..." : "健康檢查"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </PixelCard>
    </OpenClawPageShell>
  );
}
