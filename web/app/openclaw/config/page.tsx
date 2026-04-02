"use client";

import { useEffect, useState, useTransition } from "react";

import { OpenClawInstancePicker } from "@/components/openclaw-instance-picker";
import { OpenClawPageShell } from "@/components/openclaw-page-shell";
import { PixelCard } from "@/components/pixel-card";
import {
  fetchOpenClawConfig,
  fetchOpenClawInstances,
  setOpenClawConfig,
  validateOpenClawConfig
} from "@/lib/api";
import type {
  OpenClawConfigResponse,
  OpenClawConfigValidationResponse,
  OpenClawInstanceResponse
} from "@/lib/types";

const CONFIG_ROLES = [
  { name: "Chief Lobster", tagline: "配置觀察", status: "running", quote: "我會先讀取指定 path 的值，再決定是否修改。" },
  { name: "Config Clerk", tagline: "安全輸入", status: "ready", quote: "畫面只接受合法 JSON，避免把錯誤格式直接送進 Gateway。" },
  { name: "Validator", tagline: "變更驗證", status: "ready", quote: "這裡的 validate 會用 dry-run 驗證這次變更，不會真的寫入。" }
];

export default function OpenClawConfigPage() {
  const [instances, setInstances] = useState<OpenClawInstanceResponse[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState("");
  const [path, setPath] = useState("agents.default");
  const [editorValue, setEditorValue] = useState("{}");
  const [currentConfig, setCurrentConfig] = useState<OpenClawConfigResponse | null>(null);
  const [validation, setValidation] = useState<OpenClawConfigValidationResponse | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      try {
        const instancePayload = await fetchOpenClawInstances();
        setInstances(instancePayload);
        setSelectedInstanceId(instancePayload[0]?.id ?? "");
        setError("");
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "無法載入 Config 頁");
      }
    });
  }, [startTransition]);

  function parseEditorValue() {
    return JSON.parse(editorValue);
  }

  async function handleLoadConfig() {
    if (!selectedInstanceId) {
      setError("請先建立 OpenClaw Instance。");
      return;
    }

    setError("");
    setMessage("");

    startTransition(async () => {
      try {
        const result = await fetchOpenClawConfig(selectedInstanceId, path);
        setCurrentConfig(result);
        setEditorValue(JSON.stringify(result.value, null, 2));
        setMessage(`已載入 ${result.path}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "載入 Config 失敗");
      }
    });
  }

  async function handleValidate() {
    if (!selectedInstanceId) {
      setError("請先建立 OpenClaw Instance。");
      return;
    }

    setError("");
    setMessage("");

    try {
      const result = await validateOpenClawConfig({
        instance_id: selectedInstanceId,
        path,
        value: parseEditorValue()
      });
      setValidation(result);
      setMessage(result.valid ? "Config validate 通過。" : "Config validate 未通過。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Config validate 失敗");
    }
  }

  async function handleSave() {
    if (!selectedInstanceId) {
      setError("請先建立 OpenClaw Instance。");
      return;
    }

    setError("");
    setMessage("");

    try {
      const result = await setOpenClawConfig({
        instance_id: selectedInstanceId,
        path,
        value: parseEditorValue()
      });
      setCurrentConfig(result);
      setMessage(`已更新 ${result.path}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "保存 Config 失敗");
    }
  }

  return (
    <OpenClawPageShell
      title="OpenClaw Config 管理"
      description="Config 頁支援依 path 讀取、dry-run 驗證與寫入。Phase 1 以安全表單為主，不做即時跟隨更新。"
      roles={CONFIG_ROLES}
    >
      <PixelCard title="Config 控制台" eyebrow="Config">
        <div className="grid gap-4 lg:grid-cols-[280px_1fr_auto_auto_auto]">
          <OpenClawInstancePicker
            instances={instances}
            value={selectedInstanceId}
            onChange={setSelectedInstanceId}
          />
          <input
            value={path}
            onChange={(event) => setPath(event.target.value)}
            className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
            placeholder="設定路徑"
          />
          <button
            type="button"
            onClick={handleLoadConfig}
            className="pixel-button bg-teal px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
          >
            讀取
          </button>
          <button
            type="button"
            onClick={handleValidate}
            className="pixel-button bg-gold px-4 py-3 text-sm font-black tracking-[0.08em] text-ink"
          >
            Validate
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="pixel-button bg-coral px-4 py-3 text-sm font-black tracking-[0.08em] text-white"
          >
            保存
          </button>
        </div>
        <div className="mt-4 border-4 border-ink bg-white p-4 text-sm leading-7 text-slate-700">
          {error ? <span className="text-coral">{error}</span> : message || "請輸入合法 JSON。Validate 會走 dry-run，不會真的寫入設定。"}
        </div>
      </PixelCard>

      <PixelCard title="JSON Editor" eyebrow="Payload">
        <textarea
          value={editorValue}
          onChange={(event) => setEditorValue(event.target.value)}
          className="min-h-[280px] w-full border-4 border-ink bg-sand px-4 py-3 font-mono text-sm outline-none"
        />
      </PixelCard>

      <div className="grid gap-5 xl:grid-cols-2">
        <PixelCard title="目前 Config" eyebrow="Loaded">
          <div className="text-sm leading-7 text-slate-700">
            {currentConfig ? (
              <>
                <p>Path：{currentConfig.path}</p>
                <pre className="mt-4 overflow-x-auto border-4 border-ink bg-white p-4 text-xs">
                  {JSON.stringify(currentConfig.value, null, 2)}
                </pre>
              </>
            ) : (
              <p>{isPending ? "正在初始化 Config 頁..." : "尚未讀取任何 Config。"} </p>
            )}
          </div>
        </PixelCard>

        <PixelCard title="Validate 結果" eyebrow="Validation">
          {validation ? (
            <div className="space-y-3">
              <p className="text-sm font-black tracking-[0.08em]">{validation.valid ? "通過" : "未通過"}</p>
              <div className="space-y-2 text-sm text-slate-700">
                {validation.messages.length === 0 ? (
                  <p>這次 validate 沒有額外訊息。</p>
                ) : (
                  validation.messages.map((messageItem) => (
                    <div key={messageItem} className="border-4 border-ink bg-white p-3">
                      {messageItem}
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">尚未執行 validate。</p>
          )}
        </PixelCard>
      </div>
    </OpenClawPageShell>
  );
}
