"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import { fetchOpenClawDevices, fetchOpenClawInstances, runOpenClawDeviceAction } from "@/lib/api";
import type { OpenClawDeviceSummary, OpenClawInstanceResponse } from "@/lib/types";

const DEVICE_ROLES = [
  { name: "Chief Lobster", tagline: "設備巡檢", status: "running", quote: "先確認目前是 pending 還是 paired，再決定要 approve、reject 還是 revoke。" },
  { name: "Device Guard", tagline: "授權處理", status: "ready", quote: "每個按鈕都會只鎖住自己，避免整頁操作被一起卡住。" },
  { name: "Audit Scout", tagline: "錯誤回傳", status: "ready", quote: "底層 CLI 的錯誤會直接回到畫面，方便快速診斷。" }
];

export default function OpenClawDevicesPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [devices, setDevices] = useState<OpenClawDeviceSummary[]>([]);
  const [busyActionKey, setBusyActionKey] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  async function loadDevices(instanceId: string) {
    if (!instanceId) {
      setDevices([]);
      return;
    }
    setDevices(await fetchOpenClawDevices(instanceId));
  }

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        const nextInstanceId = instancePayload[0]?.id ?? "";
        setSelectedInstanceId((current) => current || nextInstanceId);
        if (nextInstanceId) {
          await loadDevices(nextInstanceId);
        }
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 Device 清單");
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!selectedInstanceId) {
      return;
    }

    startTransition(async () => {
      try {
        await loadDevices(selectedInstanceId);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法切換 Device 清單");
      }
    });
  }, [selectedInstanceId, startTransition]);

  async function handleDeviceAction(action: "approve" | "reject" | "revoke", deviceId: string) {
    const busyKey = `${action}:${deviceId}`;
    setBusyActionKey(busyKey);
    setError("");
    setMessage("");

    try {
      await runOpenClawDeviceAction(action, deviceId, selectedInstanceId);
      await loadDevices(selectedInstanceId);
      setMessage(`Device ${action} 已完成。`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `Device ${action} 失敗`);
    } finally {
      setBusyActionKey("");
    }
  }

  return (
    <OpenClawPageShell
      title="OpenClaw Device 管理"
      description="這裡會同時顯示 pending 與 paired device。每個操作都會保留審計紀錄，且按鈕只鎖定目前正在處理的那台設備。"
      roles={DEVICE_ROLES}
    >
      <PixelCard title="Instance 切換" eyebrow="Devices">
        <div className="grid gap-4 lg:grid-cols-[280px_auto_1fr]">
          <OpenClawInstancePicker
            instances={instances}
            value={selectedInstanceId}
            onChange={setSelectedInstanceId}
          />
          <button
            type="button"
            onClick={() => selectedInstanceId && loadDevices(selectedInstanceId)}
            className="pixel-button bg-teal px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
          >
            重新整理
          </button>
          <div className="border-4 border-ink bg-white px-4 py-3 text-sm text-slate-700">
            {error ? <span className="text-coral">{error}</span> : message || "點擊按鈕後，只會鎖住對應設備的操作狀態。"}
          </div>
        </div>
      </PixelCard>

      <PixelCard title="Device 清單" eyebrow="Pending + Paired">
        {instances.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            先建立 OpenClaw Instance，才能讀取 Device 狀態。
          </div>
        ) : devices.length === 0 ? (
          <div className="border-4 border-dashed border-slate-300 p-4 text-sm text-slate-500">
            {isPending ? "正在同步 Device 清單..." : "目前沒有待顯示的 Device。"}
          </div>
        ) : (
          <div className="space-y-3">
            {devices.map((device) => (
              <article key={device.id} className="border-4 border-ink bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-black tracking-[0.08em]">{device.name}</h3>
                    <p className="mt-1 text-xs text-slate-500">{device.platform ?? "未知平台"}</p>
                  </div>
                  <StatusPill status={device.status} />
                </div>

                <div className="mt-3 text-sm text-slate-700">
                  待處理動作：{device.pending_action ?? "無"}
                </div>

                <div className="mt-4 flex flex-wrap gap-3">
                  {buildDeviceActions(device.status).map((action) => {
                    const busy = busyActionKey === `${action}:${device.id}`;
                    return (
                      <button
                        key={action}
                        type="button"
                        onClick={() => handleDeviceAction(action, device.id)}
                        disabled={busy}
                        className="pixel-button bg-ink px-4 py-3 text-sm font-black tracking-[0.08em] text-sand disabled:opacity-60"
                      >
                        {busy ? `${action} 中...` : action}
                      </button>
                    );
                  })}
                </div>
              </article>
            ))}
          </div>
        )}
      </PixelCard>
    </OpenClawPageShell>
  );
}

function buildDeviceActions(status: string) {
  // pending 裝置可 approve / reject / revoke；paired 裝置主要保留 revoke。
  if (status === "pending") {
    return ["approve", "reject", "revoke"] as const;
  }

  return ["revoke"] as const;
}
