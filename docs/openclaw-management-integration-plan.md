# OpenClaw 管理能力整合方案

## 0. 本次 Phase 1 MVP 已採用的裁剪決策

目前 repo 已依本文件先落地 Phase 1 MVP，實際採用以下裁剪：

- 只做 `CLI Wrapper + Hooks`
- 只支援 `Gateway URL + Token`
- 不做 RPC、Channels、Approvals、即時 log stream、SSH、多 auth mode
- 不做登入與 RBAC，只保留後端集中代理與審計紀錄
- 新增本專案自己的操作審計 API：`GET /api/v1/openclaw/operations`

實際已落地的頁面為：

- `openclaw`
- `openclaw/instances`
- `openclaw/agents`
- `openclaw/devices`
- `openclaw/config`
- `openclaw/logs`
- `openclaw/actions`

以下規劃仍保留為後續階段方向，不視為本輪未完成：

- bindings 深度管理
- Channels 與 Pairing / QR
- Approvals 專頁
- Gateway RPC client 與即時事件流

## 1. 文件目的

本文件描述如何把官方 `OpenClaw` 的管理能力整合進本專案 `OpenClaw 智能辦公室`，讓本專案從「文件搜索與整理工作台」擴充為「業務系統中的 OpenClaw 管理台 + 任務分發台」。

本方案的重點不是把 OpenClaw 當成前端元件嵌入，而是把 OpenClaw 當成一個獨立運行的控制平面服務，由本專案提供：

- 統一管理入口
- 權限與審批封裝
- 業務事件到 OpenClaw 的任務分發
- 多實例、多 Agent、多通道的營運視圖

---

## 2. 背景與判斷

### 2.1 當前專案狀態

目前本專案主要能力為：

- `web/`：Next.js 工作台
- `api/`：FastAPI 後端
- 既有流程聚焦於本地資料源、搜索、摘要、報告輸出

也就是說，現有系統是「智能辦公工作台」，不是 OpenClaw 官方 Gateway 的管理面。

### 2.2 官方 OpenClaw 的產品型態

依官方文件，OpenClaw 目前是以獨立運行的 `Gateway + CLI + Control UI + WebSocket Protocol + Hooks` 為核心的系統，不是單純以 SDK 形式提供。

官方可用的管理入口包括：

- Control UI
- CLI
- Gateway WebSocket RPC
- Hooks / Webhooks

因此，最合理的整合方式是：

- 把 OpenClaw 視為外部服務
- 由本專案提供一層 BFF / Admin Console
- 由本專案代理管理操作與業務事件

### 2.3 為什麼不建議直接嵌官方 UI

不建議直接把官方 Control UI 當成你系統中的內嵌頁面，原因包括：

- 官方 UI 的安全模型建立在 Gateway WebSocket 與 device auth 上
- 遠端部署有 origin、token、pairing 等限制
- 官方文件明確限制 `gatewayUrl` 為 top-level window 使用情境
- 你的業務系統通常還需要自己的 RBAC、審計與操作紀錄

因此，應由本專案自行建置管理頁，後端再對接 OpenClaw。

---

## 3. 目標與非目標

### 3.1 目標

本方案目標如下：

- 在本專案中統一管理一個或多個 OpenClaw 實例
- 管理 OpenClaw Agents、Channels、Devices、Approvals、Config、Logs
- 讓業務系統可透過本專案向 OpenClaw 指派任務
- 將 OpenClaw 的控制能力納入本專案的 UI、權限與審計體系

### 3.2 非目標

第一階段不處理以下事項：

- 直接取代 OpenClaw 官方全部 Control UI 能力
- 完整重建官方即時聊天介面
- 一開始就實作完整 Gateway WebSocket 客戶端
- 企業級多租戶權限矩陣
- 所有 OpenClaw 外掛與通道的全覆蓋支持

---

## 4. 總體整合策略

### 4.1 核心策略

採用「OpenClaw 獨立部署，本專案負責代理管理」模式。

```text
Browser
  -> OpenClaw 智能辦公室 Web
  -> OpenClaw 智能辦公室 API
  -> OpenClaw Adapter
     -> OpenClaw CLI
     -> OpenClaw Gateway RPC
     -> OpenClaw Hooks
  -> OpenClaw Gateway
```

### 4.2 分層原則

本專案內部分層如下：

- `routers/`：提供本專案自己的 OpenClaw 管理 API
- `services/`：封裝業務流程與管理編排
- `providers/`：必要時容納與 OpenClaw 或其他外部服務的底層協定封裝
- `repositories/`：保存本專案自己的 OpenClaw 實例資訊、操作紀錄與快照
- `web/`：提供管理介面與業務整合入口

### 4.3 技術路線

建議分兩階段整合：

1. 先用 `CLI Wrapper + Hooks` 做 MVP
2. 再補 `Gateway WebSocket RPC` 做即時控制與事件流

這樣可同時兼顧：

- 落地速度
- 安全性
- 後續可演進性

---

## 5. 為什麼先走 CLI Wrapper

第一階段優先包裝官方 CLI，而不是直接從第一天建立完整 WebSocket 控制客戶端，原因如下：

- 官方 CLI 已覆蓋多數管理動作
- CLI 語義清楚，便於 API 映射
- 可以快速驗證管理需求與頁面結構
- 可減少初期協議實作風險
- 缺少 CLI 的部分仍可透過 `openclaw gateway call` 補足

第一階段建議覆蓋的 CLI 能力：

- `openclaw gateway status`
- `openclaw gateway health`
- `openclaw gateway probe`
- `openclaw agents list`
- `openclaw agents bindings`
- `openclaw devices list`
- `openclaw approvals`
- `openclaw logs`
- `openclaw config get`
- `openclaw config set`
- `openclaw config validate`

---

## 6. 為什麼還需要 Hooks

管理面與業務面應分離：

- 管理面負責配置、審批、觀察
- 業務面負責發任務給 Agent

業務系統若要驅動 OpenClaw，不應全都走 CLI；更自然的做法是走 OpenClaw Hooks。

建議使用：

- `POST /hooks/wake`
- `POST /hooks/agent`

這樣你的業務後端可以把事件映射成：

- 喚醒某個 Agent
- 指定 Agent 執行一個業務任務
- 指定 `agentId`、`sessionKey`、`deliver`、`channel`

---

## 7. 系統架構設計

### 7.1 邏輯元件

本方案新增四個核心模組：

#### A. OpenClaw Instance Registry

用來管理多個 OpenClaw 實例，例如：

- 測試環境實例
- 正式環境實例
- 特定團隊專用實例

負責記錄：

- 基本名稱
- Gateway URL
- 驗證方式
- SSH 目標
- 是否啟用
- 最新健康狀態

#### B. OpenClaw Adapter Layer

作為本專案與 OpenClaw 的橋樑。

拆成兩層：

- `OpenClawCliAdapter`
- `OpenClawRpcAdapter`

其中：

- CLI Adapter 負責第一階段主流程
- RPC Adapter 負責即時與細粒度能力

#### C. OpenClaw Management Service

統一封裝各類管理流程，例如：

- 讀取狀態
- 建立 Agent
- 綁定通道
- 發起設備批准
- 讀寫配置
- 取得日誌

#### D. OpenClaw Hook Dispatch Service

負責將本專案中的業務事件轉換為 OpenClaw 任務，例如：

- 新工單進入
- 新通知需要處理
- 某份文件需要摘要
- 某客戶訊息需交給指定 Agent

### 7.2 部署拓撲

建議部署拓撲如下：

```text
使用者瀏覽器
  -> 本專案 Web
  -> 本專案 API
     -> OpenClaw 管理資料庫
     -> OpenClaw Gateway 1
     -> OpenClaw Gateway 2
```

補充說明：

- 前端不直接持有 OpenClaw token
- 前端不直接連官方 Gateway
- 所有敏感操作由本專案後端代為執行

---

## 8. API 設計建議

### 8.1 API 分組

建議新增以下 API 路由：

- `/api/v1/openclaw/instances`
- `/api/v1/openclaw/instances/{instance_id}/health`
- `/api/v1/openclaw/agents`
- `/api/v1/openclaw/agents/{agent_id}/bindings`
- `/api/v1/openclaw/channels`
- `/api/v1/openclaw/devices`
- `/api/v1/openclaw/approvals`
- `/api/v1/openclaw/config`
- `/api/v1/openclaw/logs`
- `/api/v1/openclaw/hooks/agent`
- `/api/v1/openclaw/hooks/wake`

### 8.2 建議的第一期 API

#### 實例管理

- `GET /api/v1/openclaw/instances`
- `POST /api/v1/openclaw/instances`
- `PATCH /api/v1/openclaw/instances/{instance_id}`
- `GET /api/v1/openclaw/instances/{instance_id}/health`

#### Agent 管理

- `GET /api/v1/openclaw/agents?instanceId=...`
- `POST /api/v1/openclaw/agents`
- `GET /api/v1/openclaw/agents/{agent_id}/bindings`
- `POST /api/v1/openclaw/agents/{agent_id}/bindings`
- `DELETE /api/v1/openclaw/agents/{agent_id}/bindings/{binding_id}`

#### Device 管理

- `GET /api/v1/openclaw/devices?instanceId=...`
- `POST /api/v1/openclaw/devices/{device_id}/approve`
- `POST /api/v1/openclaw/devices/{device_id}/reject`
- `POST /api/v1/openclaw/devices/{device_id}/revoke`

#### Config 與 Logs

- `GET /api/v1/openclaw/config?instanceId=...&path=...`
- `POST /api/v1/openclaw/config/set`
- `POST /api/v1/openclaw/config/validate`
- `GET /api/v1/openclaw/logs?instanceId=...&limit=200`

#### Hook 派發

- `POST /api/v1/openclaw/hooks/agent`
- `POST /api/v1/openclaw/hooks/wake`

### 8.3 回應設計原則

所有 OpenClaw 相關 API 都應採用一致的回應結構，至少包含：

- `success`
- `data`
- `error`
- `meta`

其中：

- `error` 應保留底層 CLI 或 RPC 的可診斷訊息
- `meta` 可攜帶 instance id、執行耗時、來源模式
- `sourceMode` 建議標示 `cli`、`rpc` 或 `hooks`

---

## 9. 資料模型設計

### 9.1 建議資料表

建議在本專案資料庫新增以下資料表：

- `openclaw_instances`
- `openclaw_instance_secrets`
- `openclaw_cached_snapshots`
- `openclaw_operation_logs`
- `openclaw_project_bindings`

### 9.2 openclaw_instances

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | TEXT | 主鍵 |
| name | TEXT | 實例名稱 |
| gateway_url | TEXT | Gateway 位址 |
| auth_mode | TEXT | `token` / `password` / `ssh` |
| ssh_target | TEXT | SSH 連線目標 |
| is_active | INTEGER | 是否啟用 |
| last_health_status | TEXT | 最近健康狀態 |
| last_health_checked_at | TEXT | 最近檢查時間 |
| created_at | TEXT | 建立時間 |
| updated_at | TEXT | 更新時間 |

### 9.3 openclaw_instance_secrets

用於保存本專案對 OpenClaw 的安全憑證引用。

建議只保存：

- token 的 SecretRef 或安全引用
- 不在前端暴露原文密鑰

### 9.4 openclaw_cached_snapshots

用於保存最近一次同步後的快照資料，例如：

- agent 清單
- device 清單
- channel 狀態
- config 摘要

用途：

- 提供 UI 快速載入
- 降低每次頁面切換都即時打 Gateway 的壓力
- 做簡單歷史對比

### 9.5 openclaw_operation_logs

記錄管理操作審計資訊，例如：

- 哪個使用者
- 對哪個實例
- 進行何種操作
- 成功或失敗
- 錯誤訊息
- 請求與回應摘要

### 9.6 openclaw_project_bindings

用來描述「你的業務系統」與「OpenClaw Agent / Instance」的對應關係。

例如：

- 哪個業務專案使用哪個 OpenClaw Instance
- 哪個部門對應哪個預設 Agent
- 哪些事件應該路由到哪個 Agent

---

## 10. 後端模組拆分建議

### 10.1 建議新增檔案

建議新增以下後端模組：

- `api/app/routers/openclaw_instances.py`
- `api/app/routers/openclaw_agents.py`
- `api/app/routers/openclaw_channels.py`
- `api/app/routers/openclaw_devices.py`
- `api/app/routers/openclaw_approvals.py`
- `api/app/routers/openclaw_config.py`
- `api/app/routers/openclaw_logs.py`
- `api/app/routers/openclaw_hooks.py`
- `api/app/services/openclaw_service.py`
- `api/app/services/openclaw_cli_adapter.py`
- `api/app/services/openclaw_rpc_adapter.py`
- `api/app/services/openclaw_hook_service.py`
- `api/app/repositories/openclaw_instance_repository.py`
- `api/app/repositories/openclaw_operation_log_repository.py`
- `api/app/schemas/openclaw_common.py`
- `api/app/schemas/openclaw_instance.py`
- `api/app/schemas/openclaw_agent.py`
- `api/app/schemas/openclaw_device.py`
- `api/app/schemas/openclaw_config.py`
- `api/app/schemas/openclaw_hook.py`

### 10.2 模組責任

#### Router

負責：

- HTTP 參數驗證
- 錯誤轉換
- 回應格式統一

#### Service

負責：

- 管理流程編排
- 選擇 CLI / RPC / Hooks 路徑
- 審計寫入
- 快照更新

#### Repository

負責：

- 本專案自己的資料持久化
- 不直接承擔 OpenClaw 控制流程

#### Adapter

負責：

- 與 OpenClaw 互動
- 底層指令與協議封裝
- 統一轉換回本專案 schema

---

## 11. 前端頁面規劃

### 11.1 建議頁面

建議在 `web/app/` 下新增：

- `openclaw/page.tsx`
- `openclaw/instances/page.tsx`
- `openclaw/agents/page.tsx`
- `openclaw/channels/page.tsx`
- `openclaw/devices/page.tsx`
- `openclaw/config/page.tsx`
- `openclaw/logs/page.tsx`
- `openclaw/actions/page.tsx`

### 11.2 各頁職責

#### Overview

顯示：

- Instance 狀態摘要
- 健康檢查結果
- Agent 數量
- Device 待審批數
- Channel 狀態
- 最近操作紀錄

#### Instances

負責：

- 新增 OpenClaw 實例
- 編輯 Gateway URL 與認證模式
- 啟用或停用實例

#### Agents

負責：

- 顯示 Agent 清單
- 建立 Agent
- 查看與調整 bindings

#### Channels

負責：

- 顯示各通道狀態
- 顯示是否已登入
- 提供 QR / login 流程入口

#### Devices

負責：

- 顯示待審批設備
- 同意、拒絕、撤銷設備授權

#### Config

負責：

- 顯示常用配置
- 提供安全表單修改
- 顯示 config validate 結果

#### Logs

負責：

- 顯示 Gateway log
- 支援 follow、limit、時間格式

#### Actions

負責：

- 手動發送 `/hooks/agent`
- 手動發送 `/hooks/wake`
- 驗證業務事件是否成功觸發 Agent

---

## 12. 權限與安全設計

### 12.1 安全原則

整合 OpenClaw 時必須遵守以下原則：

- 不把 Gateway token 直接暴露給瀏覽器
- 不讓前端直接呼叫 OpenClaw CLI
- 不讓前端直接連 Gateway WebSocket
- 所有管理操作都經過本專案後端
- 所有敏感操作都保留審計紀錄

### 12.2 角色建議

本專案可先定義三種角色：

- `viewer`
- `operator`
- `admin`

建議對應能力：

- `viewer`：只能看狀態與日誌
- `operator`：可執行 Agent、Device、Hook 類操作
- `admin`：可變更 config、instance、approvals

### 12.3 與 OpenClaw scope 的映射

OpenClaw 本身有 operator scope，建議本專案做二次封裝：

- `viewer` -> 映射到 `operator.read`
- `operator` -> 映射到 `operator.write`
- `admin` -> 視情況加上 `operator.admin`、`operator.approvals`、`operator.pairing`

### 12.4 不建議採用的方式

避免以下做法：

- 直接在瀏覽器保存 OpenClaw token
- 直接把官方 Control UI 內嵌進本系統
- 使用過度寬鬆的 origin 設定
- 使用 `dangerouslyDisableDeviceAuth`

---

## 13. CLI 與 RPC 的分工

### 13.1 第一階段以 CLI 為主

適合 CLI 的能力：

- 狀態讀取
- 基本 Agent 管理
- Device 清單與操作
- Config 讀寫
- Logs 取得

### 13.2 第二階段補 RPC

適合 RPC 的能力：

- 即時事件流
- 即時 log follow
- 更細粒度的狀態同步
- 即時 QR / pairing 流程
- 後續聊天與 session 觀測

### 13.3 決策原則

若某功能符合以下任一條件，優先進 RPC：

- 需要低延遲即時反映
- 需要持續推送事件
- CLI 輸出不穩定或不完整
- 必須與 Gateway 狀態保持長連線同步

---

## 14. Hook 業務整合設計

### 14.1 使用情境

當業務系統中發生事件時，可以由本專案對 OpenClaw 派發 Hook 任務。

典型情境：

- 新客服訊息進入後，交由指定 Agent 草擬回應
- 某專案文件上傳後，要求 Agent 做整理摘要
- 某提醒事件發生後，要求 Agent 主動發送通知
- 某工單進入特定狀態後，要求 Agent 進行下一步操作

### 14.2 建議映射方式

本專案後端負責把業務事件轉換成統一格式：

- `instanceId`
- `agentId`
- `sessionKey`
- `message`
- `deliver`
- `channel`
- `to`
- `metadata`

然後由 `openclaw_hook_service.py` 派發給對應的 OpenClaw Hook。

### 14.3 sessionKey 規範

建議本專案統一定義 session key 規範，例如：

```text
project:{projectId}
ticket:{ticketId}
customer:{customerId}
doc:{documentId}
```

這樣可讓 OpenClaw 在 session 上維持穩定上下文。

---

## 15. 第一階段實作範圍

### 15.1 MVP 功能

第一階段建議只做以下能力：

- OpenClaw Instance 管理
- Gateway Health / Status
- Agent 清單與建立
- Device 清單與批准
- Config 讀寫與 validate
- Logs 查閱
- Hook 派發

### 15.2 第一階段不做

先不做以下能力：

- 內建即時聊天頁
- 所有 Channel 的完整登入流程
- 多節點畫布能力
- Skills 編輯器
- Cron 與 Schedule 全量 UI
- 完整遠端配對流程重建

---

## 16. 第二階段與第三階段規劃

### 16.1 第二階段

目標：

- 補 Channels 頁
- 補 Pairing / QR 狀態觀測
- 補 Approvals 管理
- 加入快照同步與排程健康檢查

### 16.2 第三階段

目標：

- 引入 Gateway WebSocket RPC client
- 做即時 log stream
- 做 session / chat 觀測視圖
- 支援更細粒度通道管理

---

## 17. 風險與對策

### 17.1 風險：CLI 版本變動

問題：

- 官方 CLI 輸出可能在版本升級後微調

對策：

- 優先使用 `--json`
- 在 adapter 層做集中轉換
- 增加版本檢查與 smoke test

### 17.2 風險：通道登入流程複雜

問題：

- 部分通道帶有 QR、pairing、device auth 等流程

對策：

- 第一階段不完全重建
- 先支援狀態觀測與外部流程入口
- 真正即時控制留給第二或第三階段

### 17.3 風險：安全邊界混亂

問題：

- 若讓前端直接連 Gateway，將增加 token 與 scope 外洩風險

對策：

- 全部改由本專案後端代理
- 自建 RBAC 與審計
- 明確區分 viewer / operator / admin

### 17.4 風險：管理面與業務面耦合

問題：

- 如果把管理操作與業務事件派發混在一起，後續維護會困難

對策：

- API 與 service 層清楚分組
- Management API 與 Hook Dispatch API 分開

---

## 18. 驗收標準

若要判定第一階段已完成，至少應滿足以下條件：

- 可在本專案中新增並保存 OpenClaw Instance
- 可對指定 Instance 執行健康檢查
- 可列出 Agent 與 Device 清單
- 可執行 Device approve / reject / revoke
- 可查看 OpenClaw logs
- 可透過本專案發送 `/hooks/agent` 與 `/hooks/wake`
- 敏感資訊不出現在前端
- 所有操作可寫入審計紀錄

---

## 19. 建議實作順序

建議依以下順序開發：

1. 後端資料表與 instance repository
2. CLI adapter 與 service 基礎層
3. instance / health / agents / devices API
4. Overview / Instances / Agents / Devices 頁面
5. Config / Logs API 與頁面
6. Hook Dispatch API 與 Actions 頁面
7. 操作審計與快照同步
8. 第二階段的 channels / approvals

---

## 20. 結論

本專案若要整合 OpenClaw 管理能力，最佳方案不是把 OpenClaw 當成單一函式庫導入，而是：

- 把 OpenClaw 視為獨立控制平面
- 由本專案建立管理台與代理 API
- 第一階段先走 CLI Wrapper + Hooks
- 第二階段再補 Gateway WebSocket RPC

這樣可以在不破壞現有 `搜索 -> 整理 -> 分析 -> 輸出` 產品方向的前提下，把本專案擴充成同時具備：

- 智能辦公工作台
- OpenClaw 管理台
- 業務事件到 Agent 的任務分發入口

---

## 21. 參考資料

- OpenClaw 官方首頁: <https://openclaw.ai/>
- OpenClaw 文件總覽: <https://docs.openclaw.ai/>
- CLI Reference: <https://docs.openclaw.ai/cli/index>
- Gateway CLI: <https://docs.openclaw.ai/cli/gateway>
- Gateway Protocol: <https://docs.openclaw.ai/gateway/protocol>
- Control UI: <https://docs.openclaw.ai/web/control-ui>
- Webhooks: <https://docs.openclaw.ai/automation/webhook>
- Chat Channels: <https://docs.openclaw.ai/channels>
