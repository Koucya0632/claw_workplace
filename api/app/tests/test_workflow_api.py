from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.openclaw_system_inspection_config_repository import OpenClawSystemInspectionConfigRepository
from app.repositories.openclaw_workflow_config_repository import OpenClawWorkflowConfigRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.openclaw_daily_news_config_repository import OpenClawDailyNewsConfigRepository
from app.routers import openclaw_daily_news, openclaw_instances, openclaw_system_inspection, openclaw_workflow_config, workflows
from app.schemas.openclaw_daily_news import OpenClawDailyNewsConfigResponse
from app.schemas.openclaw_instance import OpenClawInstanceSnapshotSummary, OpenClawInstanceResponse
from app.schemas.openclaw_system_inspection import OpenClawSystemInspectionConfigResponse
from app.schemas.workflow import WorkflowNewsDedupeOutput, WorkflowNewsRankOutput, WorkflowNewsSearchOutput
from app.schemas.workflow import WorkflowNewsMonitorOutput
from app.schemas.workflow import (
    WorkflowSystemInspectionLogIssue,
    WorkflowSystemInspectionLogReviewOutput,
    WorkflowSystemInspectionRiskOutput,
    WorkflowSystemInspectionVersionOutput,
)
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_service import OpenClawInstanceService
from app.services.openclaw_release_client import OpenClawReleaseClient
from app.services.workflow_service import (
    OpenClawDailyNewsConfigService,
    OpenClawSystemInspectionConfigService,
    OpenClawWorkflowConfigService,
    SearchReportWorkflowService,
    _build_news_brief_prompt,
    _build_news_dedupe_prompt,
    _build_news_monitor_prompt,
    _build_news_rank_prompt,
    _build_news_search_prompt,
    _fallback_news_dedupe_output,
    _build_system_report_prompt,
    _compact_system_log_review_output,
    _compact_system_risk_output,
    _compact_system_version_output,
    _is_agent_timeout_error,
)


class MockWorkflowCliAdapter:
    source_mode = "cli"

    def list_agents(self, instance, token: str | None) -> list[dict[str, Any]]:
        return [
            {"id": "main", "name": "Main Secretary", "status": "ready"},
            {"id": "search-agent", "name": "Search Agent", "status": "ready"},
            {"id": "organizer-agent", "name": "Organizer Agent", "status": "ready"},
            {"id": "analysis-agent", "name": "Analysis Agent", "status": "ready"},
            {"id": "report-agent", "name": "Report Agent", "status": "ready"},
            {"id": "system-inspection-agent", "name": "System Inspection Agent", "status": "ready"},
        ]

    def get_version(self) -> str:
        return "OpenClaw 2026.4.1 (da64a97)"

    def get_global_config(self, path: str) -> dict[str, Any]:
        return {"value": "2026.4.1"}

    def get_logs(self, instance, token: str | None, limit: int) -> list[dict[str, Any]]:
        return [
            {"time": "2026-04-05T09:20:00Z", "level": "warn", "message": "retrying workflow dispatch after timeout"},
            {"time": "2026-04-05T09:25:00Z", "level": "error", "message": "telegram markdown parse failed"},
        ]

    def inspect_plugin(self, plugin_id: str) -> dict[str, Any]:
        return {"id": plugin_id, "enabled": True, "status": "ready"}


class MockWorkflowHookClient:
    source_mode = "cli"

    def dispatch_agent(self, instance, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        stage_key = payload["metadata"]["stage_key"]

        if stage_key == "understand":
            text = json.dumps(
                {
                    "goal_summary": "聚焦外部網站上和『包』相關的內容。",
                    "normalized_topic": "搜尋『包』的外部說明與比較資訊",
                    "search_plan": ["先查外部網站", "再整理重點"],
                    "keywords": ["包", "方案"],
                    "target_urls": [],
                    "target_sites": ["官方網站"],
                    "target_domains": ["example.com"],
                    "must_include": ["價格"],
                    "must_exclude": ["舊版"],
                    "focus_points": ["差異", "重點"],
                    "output_format": "bullets",
                    "include_project_sources": True,
                },
                ensure_ascii=False,
            )
        elif stage_key == "search" and payload["metadata"].get("workflow_type") == "web_search":
            text = json.dumps(
                {
                    "summary": "已找到外部網站與專案索引裡最相關的內容。",
                    "search_queries": ["包 方案 價格", "site:example.com 包"],
                    "sources": [
                        {
                            "title": "官方包方案",
                            "source_type": "web",
                            "snippet": "官方網站整理了各種包方案與價格",
                            "reason": "直接命中主題與重點欄位",
                            "matched_keywords": ["包", "價格"],
                            "url": "https://example.com/package",
                            "domain": "example.com",
                        },
                        {
                            "title": "support-package.md",
                            "source_type": "project",
                            "snippet": "這是一份關於包的客服說明",
                            "reason": "可以補強內部客服口徑",
                            "matched_keywords": ["包"],
                            "source_name": "Support Docs",
                            "document_id": "doc_1",
                            "relative_path": "support/support-package.md",
                        },
                    ],
                },
                ensure_ascii=False,
            )
        elif stage_key == "filter":
            text = json.dumps(
                {
                    "summary": "已排除不相關內容，只保留與價格與差異最相關的來源。",
                    "kept_sources": [
                        {
                            "title": "官方包方案",
                            "source_type": "web",
                            "snippet": "官方網站整理了各種包方案與價格",
                            "reason": "最直接回答價格與差異",
                            "matched_keywords": ["包", "價格"],
                            "url": "https://example.com/package",
                            "domain": "example.com",
                        }
                    ],
                    "discarded_count": 1,
                    "extracted_points": ["官方頁面提供最新方案差異。"],
                    "focus_answers": ["價格與差異都集中在官方包方案頁。"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "format":
            text = json.dumps(
                {
                    "title": "『包』Web Search 整理",
                    "requested_format": "bullets",
                    "summary": "已完成外網與專案索引的條件化搜尋整理。",
                    "key_points": ["官方頁面提供最新方案資訊。"],
                    "focus_answers": ["若重點是價格與差異，官方頁最值得先看。"],
                    "included_sources": [
                        {
                            "title": "官方包方案",
                            "source_type": "web",
                            "snippet": "官方網站整理了各種包方案與價格",
                            "reason": "最直接回答價格與差異",
                            "matched_keywords": ["包", "價格"],
                            "url": "https://example.com/package",
                            "domain": "example.com",
                        }
                    ],
                    "applied_filters": ["必須包含：價格", "排除：舊版"],
                    "structured_output": "- 官方頁最相關\n- 已過濾舊版內容",
                    "markdown": "# 『包』Web Search 整理\n\n- 官方頁最相關\n- 已過濾舊版內容\n",
                },
                ensure_ascii=False,
            )
        elif stage_key == "search":
            text = json.dumps(
                {
                    "summary": "已找到客服相關文件。",
                    "candidates": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "relative_path": "support/support-package.md",
                            "source_id": "src_1",
                            "source_name": "Support Docs",
                            "snippet": "這是一份關於包的客服說明",
                            "reason": "直接命中查詢關鍵字",
                        }
                    ],
                    "selected_documents": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "relative_path": "support/support-package.md",
                            "source_id": "src_1",
                            "source_name": "Support Docs",
                            "snippet": "這是一份關於包的客服說明",
                            "reason": "內容最完整",
                        }
                    ],
                    "source_overview": ["Support Docs 提供最完整的客服上下文。"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "analysis":
            text = json.dumps(
                {
                    "summary": "分析顯示使用者想找的是與『包』相關的客服說明與處理方式。",
                    "highlights": ["文件已說明處理步驟。"],
                    "risks": ["若只看單一文件可能漏掉限制條件。"],
                    "todos": ["確認是否需要補充最新政策。"],
                    "evidence": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "quote": "這是一份關於包的客服說明",
                            "reason": "直接支持主要結論",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        elif stage_key == "monitor":
            text = json.dumps(
                {
                    "goal_summary": "追蹤 AI 與半導體最新重大新聞。",
                    "tracking_scope": ["AI", "半導體", "日本"],
                    "search_queries": ["AI semiconductor Japan latest news"],
                    "watch_focus": ["政策", "產品發表", "公司動向"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "dedupe":
            text = json.dumps(
                {
                    "summary": "已合併同事件報導並移除重複來源。",
                    "unique_stories": [
                        {
                            "title": "NVIDIA 發布新一代 AI 平台",
                            "summary": "新平台鎖定企業 AI 基礎設施升級。",
                            "importance_reason": "直接影響 AI 產業與供應鏈預期。",
                            "possible_impact": "可能帶動上游供應鏈與競品應對。",
                            "sources": [
                                {
                                    "title": "NVIDIA unveils platform",
                                    "snippet": "NVIDIA introduced a new platform...",
                                    "source_name": "Reuters",
                                    "reason": "權威主流來源",
                                    "published_at": "2026-04-04T08:00:00Z",
                                    "url": "https://example.com/nvidia",
                                    "domain": "example.com",
                                }
                            ],
                            "published_at": "2026-04-04T08:00:00Z",
                            "background": "NVIDIA 持續擴大企業 AI 佈局。",
                            "watch_points": ["企業採用速度"],
                            "event_key": "nvidia-platform",
                        }
                    ],
                    "removed_duplicates": 2,
                    "dedupe_notes": ["同事件多篇報導已合併。"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "rank":
            text = json.dumps(
                {
                    "summary": "已依重要性完成新聞排序。",
                    "top_stories": [
                        {
                            "title": "NVIDIA 發布新一代 AI 平台",
                            "summary": "新平台鎖定企業 AI 基礎設施升級。",
                            "importance_reason": "直接影響 AI 產業與供應鏈預期。",
                            "possible_impact": "可能帶動上游供應鏈與競品應對。",
                            "sources": [
                                {
                                    "title": "NVIDIA unveils platform",
                                    "snippet": "NVIDIA introduced a new platform...",
                                    "source_name": "Reuters",
                                    "reason": "權威主流來源",
                                    "published_at": "2026-04-04T08:00:00Z",
                                    "url": "https://example.com/nvidia",
                                    "domain": "example.com",
                                }
                            ],
                            "published_at": "2026-04-04T08:00:00Z",
                            "background": "NVIDIA 持續擴大企業 AI 佈局。",
                            "watch_points": ["企業採用速度"],
                            "event_key": "nvidia-platform",
                        }
                    ],
                    "other_stories": [],
                    "trend_summary": "AI 基礎設施與半導體供應鏈仍是今日焦點。",
                    "watch_items": ["觀察主要供應鏈廠商回應。"],
                    "uncertainties": ["部分供應鏈影響仍待財報確認。"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "brief":
            text = json.dumps(
                {
                    "title": "每日新聞 Brief",
                    "top_stories": [
                        {
                            "title": "NVIDIA 發布新一代 AI 平台",
                            "summary": "新平台鎖定企業 AI 基礎設施升級。",
                            "importance_reason": "直接影響 AI 產業與供應鏈預期。",
                            "possible_impact": "可能帶動上游供應鏈與競品應對。",
                            "sources": [
                                {
                                    "title": "NVIDIA unveils platform",
                                    "snippet": "NVIDIA introduced a new platform...",
                                    "source_name": "Reuters",
                                    "reason": "權威主流來源",
                                    "published_at": "2026-04-04T08:00:00Z",
                                    "url": "https://example.com/nvidia",
                                    "domain": "example.com",
                                }
                            ],
                            "published_at": "2026-04-04T08:00:00Z",
                            "background": "NVIDIA 持續擴大企業 AI 佈局。",
                            "watch_points": ["企業採用速度"],
                            "event_key": "nvidia-platform",
                        }
                    ],
                    "other_stories": [],
                    "trend_summary": "AI 基礎設施與半導體供應鏈仍是今日焦點。",
                    "watch_items": ["觀察主要供應鏈廠商回應。"],
                    "dedupe_notes": ["同事件多篇報導已合併。"],
                    "uncertainties": ["部分供應鏈影響仍待財報確認。"],
                    "raw_sources": [
                        {
                            "title": "NVIDIA unveils platform",
                            "snippet": "NVIDIA introduced a new platform...",
                            "source_name": "Reuters",
                            "reason": "權威主流來源",
                            "published_at": "2026-04-04T08:00:00Z",
                            "url": "https://example.com/nvidia",
                            "domain": "example.com",
                        }
                    ],
                    "markdown": "# 每日新聞 Brief\n\n## 一、今日最重要新聞\n1. NVIDIA 發布新一代 AI 平台\n",
                    "delivery_status": "pending",
                    "delivery_target": None,
                    "delivery_error": None,
                },
                ensure_ascii=False,
            )
        elif stage_key == "version_check":
            text = json.dumps(
                {
                    "current_version": "OpenClaw 2026.4.1 (da64a97)",
                    "latest_version": "2026.4.2",
                    "latest_version_status": "available",
                    "version_gap": "1 patch release",
                    "release_summary": ["修復 plugin 載入穩定性問題", "改善 Telegram 投遞相容性"],
                    "breaking_changes": [],
                    "deprecations": ["部分舊 plugin manifest 欄位已不建議使用"],
                    "compatibility_risks": ["升級前需確認 plugin manifest 與 workflow prompt 相容性"],
                    "affected_areas": {
                        "agent_config": ["確認 specialist agent mapping 未受影響"],
                        "tool_permissions": ["檢查 project_search / web_search 權限"],
                        "prompt_logic": ["回歸測試 system inspection 與 news brief prompts"],
                        "workflow": ["驗證 stage timeout 與 failure handling"],
                        "plugins_skills": ["確認 project-search plugin manifest 與 bridge"],
                        "ui_console": ["巡檢頁與 Daily News 頁回歸"],
                        "deployment_runtime": ["重啟 gateway 後確認 runtime config 生效"],
                    },
                    "upgrade_recommendation": "test_before_upgrade",
                    "regression_test_checklist": ["workflow smoke test", "telegram delivery test"],
                    "assumptions": ["官方 release 摘要可正常代表最新 patch 內容"],
                    "verification_steps": ["在 staging 升級後跑 smoke test"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "log_review":
            text = json.dumps(
                {
                    "summary": "近期主要問題集中在 timeout 與 Telegram Markdown 投遞。",
                    "issues": [
                        {
                            "issue_key": "timeout:dispatch_workflow_stage",
                            "category": "timeout",
                            "description": "workflow stage dispatch 偶發 timeout",
                            "frequency": 2,
                            "first_seen_at": "2026-04-05T09:10:00Z",
                            "last_seen_at": "2026-04-05T09:20:00Z",
                            "possible_root_causes": ["agent prompt 過大"],
                            "affected_components": ["workflow_dispatch"],
                            "impact_scope": "news brief 和 inspection 可能延遲",
                            "severity": "high",
                            "fix_actions": ["縮小 stage prompt", "必要時提高 timeout"],
                            "optimization_actions": ["針對高成本 stage 使用獨立 timeout"],
                            "priority": "p1",
                            "assumptions": [],
                            "verification_steps": ["重跑同類 workflow"],
                        },
                        {
                            "issue_key": "telegram_parse_entities",
                            "category": "warning",
                            "description": "Telegram Markdown parse 失敗但已有 plain text fallback",
                            "frequency": 1,
                            "first_seen_at": "2026-04-05T09:25:00Z",
                            "last_seen_at": "2026-04-05T09:25:00Z",
                            "possible_root_causes": ["Markdown 字元未完全 escape"],
                            "affected_components": ["telegram_delivery"],
                            "impact_scope": "通知可能回退為純文字",
                            "severity": "medium",
                            "fix_actions": ["保留 fallback", "後續補 escape"],
                            "optimization_actions": ["建立 Markdown sanitizer"],
                            "priority": "p2",
                            "assumptions": [],
                            "verification_steps": ["發送含特殊字元摘要"],
                        },
                    ],
                    "log_window_hours": 24,
                    "inspected_log_count": 4,
                },
                ensure_ascii=False,
            )
        elif stage_key == "risk_assessment":
            text = json.dumps(
                {
                    "summary": "建議先修 timeout 與 Telegram 格式穩定性，再評估升級到 2026.4.2。",
                    "upgrade_recommendation": "test_before_upgrade",
                    "high_priority_risks": [
                        {
                            "issue_key": "timeout:dispatch_workflow_stage",
                            "category": "timeout",
                            "description": "workflow stage dispatch 偶發 timeout",
                            "frequency": 2,
                            "first_seen_at": "2026-04-05T09:10:00Z",
                            "last_seen_at": "2026-04-05T09:20:00Z",
                            "possible_root_causes": ["agent prompt 過大"],
                            "affected_components": ["workflow_dispatch"],
                            "impact_scope": "news brief 和 inspection 可能延遲",
                            "severity": "high",
                            "fix_actions": ["縮小 stage prompt", "必要時提高 timeout"],
                            "optimization_actions": ["針對高成本 stage 使用獨立 timeout"],
                            "priority": "p1",
                            "assumptions": [],
                            "verification_steps": ["重跑同類 workflow"],
                        }
                    ],
                    "immediate_actions": ["先縮小 timeout 熱點 stage 的輸入", "在 staging 驗證 2026.4.2"],
                    "assumptions": ["目前問題主要來自 prompt / timeout，不是 gateway crash"],
                    "verification_steps": ["先做 staging smoke test 再升級"],
                },
                ensure_ascii=False,
            )
        elif stage_key == "report" and payload["metadata"].get("workflow_type") == "system_inspection":
            text = json.dumps(
                {
                    "title": "系統巡檢與風險評估報告",
                    "inspection_summary": ["目前系統可用，但仍有 timeout 與 Telegram Markdown 穩定性風險。"],
                    "version_update_check": {
                        "current_version": "OpenClaw 2026.4.1 (da64a97)",
                        "latest_version": "2026.4.2",
                        "latest_version_status": "available",
                        "version_gap": "1 patch release",
                        "release_summary": ["修復 plugin 載入穩定性問題", "改善 Telegram 投遞相容性"],
                        "breaking_changes": [],
                        "deprecations": ["部分舊 plugin manifest 欄位已不建議使用"],
                        "compatibility_risks": ["升級前需確認 plugin manifest 與 workflow prompt 相容性"],
                        "affected_areas": {
                            "agent_config": ["確認 specialist agent mapping 未受影響"],
                            "tool_permissions": ["檢查 project_search / web_search 權限"],
                            "prompt_logic": ["回歸測試 system inspection 與 news brief prompts"],
                            "workflow": ["驗證 stage timeout 與 failure handling"],
                            "plugins_skills": ["確認 project-search plugin manifest 與 bridge"],
                            "ui_console": ["巡檢頁與 Daily News 頁回歸"],
                            "deployment_runtime": ["重啟 gateway 後確認 runtime config 生效"],
                        },
                        "upgrade_recommendation": "test_before_upgrade",
                        "regression_test_checklist": ["workflow smoke test", "telegram delivery test"],
                        "assumptions": ["官方 release 摘要可正常代表最新 patch 內容"],
                        "verification_steps": ["在 staging 升級後跑 smoke test"],
                    },
                    "log_review": {
                        "summary": "近期主要問題集中在 timeout 與 Telegram Markdown 投遞。",
                        "issues": [],
                        "log_window_hours": 24,
                        "inspected_log_count": 4,
                    },
                    "high_priority_risks": [
                        {
                            "issue_key": "timeout:dispatch_workflow_stage",
                            "category": "timeout",
                            "description": "workflow stage dispatch 偶發 timeout",
                            "frequency": 2,
                            "first_seen_at": "2026-04-05T09:10:00Z",
                            "last_seen_at": "2026-04-05T09:20:00Z",
                            "possible_root_causes": ["agent prompt 過大"],
                            "affected_components": ["workflow_dispatch"],
                            "impact_scope": "news brief 和 inspection 可能延遲",
                            "severity": "high",
                            "fix_actions": ["縮小 stage prompt", "必要時提高 timeout"],
                            "optimization_actions": ["針對高成本 stage 使用獨立 timeout"],
                            "priority": "p1",
                            "assumptions": [],
                            "verification_steps": ["重跑同類 workflow"],
                        }
                    ],
                    "fix_and_optimization_actions": ["先優化高成本 stage prompt", "建立 staging 升級回歸清單"],
                    "open_questions": ["官方 patch 是否涉及更多 plugin manifest 變更"],
                    "recommended_execution_order": ["先修 timeout 熱點", "再於 staging 測 2026.4.2", "確認無回歸後再升級正式環境"],
                    "telegram_summary": "巡檢結論：先修 timeout，再測試升級到 2026.4.2。",
                    "markdown": "# 系統巡檢與風險評估報告\n\n## 1. 巡檢總結\n- 先修 timeout，再測試升級。\n",
                    "delivery_status": "pending",
                    "delivery_target": None,
                    "delivery_error": None,
                },
                ensure_ascii=False,
            )
        else:
            text = json.dumps(
                {
                    "title": "『包』相關客服工作報告",
                    "executive_summary": "已完成搜索、分析與報告整理。",
                    "highlights": ["已找到最相關來源。"],
                    "recommendations": ["優先引用 support-package.md。"],
                    "evidence": [
                        {
                            "document_id": "doc_1",
                            "filename": "support-package.md",
                            "quote": "這是一份關於包的客服說明",
                            "reason": "主要證據來源",
                        }
                    ],
                    "sections": [
                        {
                            "title": "搜索結果",
                            "summary": "已定位到主要客服文件。",
                            "bullets": ["搜尋到 1 份核心文件"],
                            "body": "文件內容足以支撐第一版報告。",
                        }
                    ],
                    "appendix": ["workflow 由三個 OpenClaw agents 串行完成。"],
                    "markdown": "# 『包』相關客服工作報告\n\n已完成搜索、分析與報告整理。\n",
                },
                ensure_ascii=False,
            )

        return {
            "runId": f"run-{stage_key}",
            "status": "ok",
            "summary": "completed",
            "result": {
                "payloads": [
                    {
                        "text": text,
                    }
                ]
            },
        }


class MockTelegramDeliveryClient:
    source_mode = "telegram_http"

    def send_markdown(self, *, chat_id: str, text: str) -> dict[str, Any]:
        return {"message_id": 123, "chat": {"id": chat_id}, "text": text}


class MockDiscordDeliveryClient:
    source_mode = "discord_http"

    def send_text(self, *, channel_id: str, text: str) -> dict[str, Any]:
        return {"message_ids": ["9001"], "channel_id": channel_id, "message_count": 1, "text": text}


class MockReleaseClient(OpenClawReleaseClient):
    def __init__(self) -> None:
        super().__init__(timeout_seconds=1)

    def fetch_release_summary(self, url: str) -> dict[str, Any]:
        return {
            "latest_version": "2026.4.2",
            "release_summary": ["修復 plugin 載入穩定性問題", "改善 Telegram 投遞相容性"],
            "raw_excerpt": "OpenClaw 2026.4.2 patch release",
            "source_url": url,
        }


def install_workflow_services() -> None:
    repository = OpenClawInstanceRepository()
    workflow_repository = WorkflowRepository()
    workflow_config_repository = OpenClawWorkflowConfigRepository()
    daily_news_repository = OpenClawDailyNewsConfigRepository()
    system_inspection_repository = OpenClawSystemInspectionConfigRepository()
    operation_log_repository = OpenClawOperationLogRepository()
    secret_cipher = OpenClawSecretCipher("test-openclaw-secret")
    cli_adapter = MockWorkflowCliAdapter()
    hook_client = MockWorkflowHookClient()
    telegram_delivery_client = MockTelegramDeliveryClient()
    discord_delivery_client = MockDiscordDeliveryClient()
    release_client = MockReleaseClient()

    openclaw_instances.instance_service = OpenClawInstanceService(
        repository=repository,
        operation_log_repository=operation_log_repository,
        secret_cipher=secret_cipher,
    )
    openclaw_workflow_config.workflow_config_service = OpenClawWorkflowConfigService(
        repository=repository,
        workflow_config_repository=workflow_config_repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
        secret_cipher=secret_cipher,
    )
    openclaw_daily_news.daily_news_service = OpenClawDailyNewsConfigService(
        repository=repository,
        daily_news_repository=daily_news_repository,
        operation_log_repository=operation_log_repository,
    )
    openclaw_system_inspection.system_inspection_service = OpenClawSystemInspectionConfigService(
        repository=repository,
        system_inspection_repository=system_inspection_repository,
        operation_log_repository=operation_log_repository,
    )
    workflows.workflow_service = SearchReportWorkflowService(
        repository=repository,
        workflow_repository=workflow_repository,
        workflow_config_repository=workflow_config_repository,
        daily_news_repository=daily_news_repository,
        system_inspection_repository=system_inspection_repository,
        operation_log_repository=operation_log_repository,
        hook_client=hook_client,
        telegram_delivery_client=telegram_delivery_client,
        discord_delivery_client=discord_delivery_client,
        cli_adapter=cli_adapter,
        release_client=release_client,
        secret_cipher=secret_cipher,
        run_inline=True,
    )


def create_instance(client: TestClient) -> str:
    response = client.post(
        "/api/v1/openclaw/instances",
        json={
            "name": "Primary Gateway",
            "gateway_url": "http://gateway.internal",
            "token": "super-secret-token",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_workflow_run_happy_path(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    config_response = client.post(
        "/api/v1/openclaw/workflow-config",
        json={
            "instance_id": instance_id,
            "controller_agent_id": "main",
            "search_agent_id": "search-agent",
            "analysis_agent_id": "analysis-agent",
            "report_agent_id": "report-agent",
            "specialist_agents": {
                "search_web": {"agent_id": "main", "enabled": False},
                "organizer": {"agent_id": "organizer-agent", "enabled": True},
                "writer": {"agent_id": "report-agent", "enabled": True},
                "test_design": {"agent_id": "", "enabled": False},
                "ui_review": {"agent_id": "", "enabled": False},
                "monitor": {"agent_id": "", "enabled": False},
                "daily_news_brief": {"agent_id": "", "enabled": False},
                "system_inspection": {"agent_id": "", "enabled": False},
            },
            "routing_rules": [],
            "handoff_policy": {
                "manual_review_required_on_conflict": True,
                "manual_review_required_on_high_risk": True,
                "max_search_retry_count": 1,
                "max_report_retry_count": 2,
                "timeout_escalation_seconds": 180,
                "fallback_mode": "controller",
            },
        },
    )
    assert config_response.status_code == 200

    create_response = client.post(
        "/api/v1/workflows/search-report",
        json={"instance_id": instance_id, "query": "包"},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] == "completed"
    assert payload["overall_progress_percent"] == 100
    assert payload["final_report"]["title"] == "『包』相關客服工作報告"
    assert [stage["stage_key"] for stage in payload["stages"]] == ["search", "analysis", "report"]
    assert payload["input_payload"]["controller_agent_id"] == "main"
    assert all(stage["status"] == "completed" for stage in payload["stages"])
    assert any(event["agent_id"] == "main" and "主控秘書" in event["message"] for event in payload["events"])
    assert any(event["message"] == "搜索資料中..." for event in payload["events"])
    assert any(event["message"] == "正在分析重點..." for event in payload["events"])
    assert any(event["message"] == "完整報告已生成，可回看全鏈路與匯出 Markdown。" for event in payload["events"])

    get_response = client.get(f"/api/v1/workflows/{payload['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == payload["id"]

    list_response = client.get("/api/v1/workflows", params={"instanceId": instance_id})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_workflow_run_requires_config(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    response = client.post(
        "/api/v1/workflows/search-report",
        json={"instance_id": instance_id, "query": "包"},
    )
    assert response.status_code == 400
    assert "尚未設定搜索、分析、報告三階段 agent" in response.json()["detail"]


def test_web_search_workflow_and_continue_to_report(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    config_response = client.post(
        "/api/v1/openclaw/workflow-config",
        json={
            "instance_id": instance_id,
            "controller_agent_id": "main",
            "search_agent_id": "search-agent",
            "analysis_agent_id": "analysis-agent",
            "report_agent_id": "report-agent",
            "specialist_agents": {
                "search_web": {"agent_id": "main", "enabled": True},
                "organizer": {"agent_id": "organizer-agent", "enabled": True},
                "writer": {"agent_id": "report-agent", "enabled": True},
                "test_design": {"agent_id": "", "enabled": False},
                "ui_review": {"agent_id": "", "enabled": False},
                "monitor": {"agent_id": "", "enabled": False},
                "daily_news_brief": {"agent_id": "", "enabled": False},
                "system_inspection": {"agent_id": "", "enabled": False},
            },
            "routing_rules": [
                {
                    "key": "prefer-web-search",
                    "label": "網址 / 網域優先派 Web 搜索代理",
                    "enabled": True,
                    "conditions": ["url", "domain", "site"],
                    "route_to": ["search_web"],
                }
            ],
            "handoff_policy": {
                "manual_review_required_on_conflict": True,
                "manual_review_required_on_high_risk": True,
                "max_search_retry_count": 1,
                "max_report_retry_count": 2,
                "timeout_escalation_seconds": 180,
                "fallback_mode": "controller",
            },
        },
    )
    assert config_response.status_code == 200

    create_response = client.post(
        "/api/v1/workflows/web-search",
        json={
            "instance_id": instance_id,
            "topic": "包",
            "target_urls": [],
            "target_sites": ["官方網站"],
            "target_domains": ["example.com"],
            "keywords": ["包", "方案"],
            "must_include": ["價格"],
            "must_exclude": ["舊版"],
            "focus_points": ["差異", "重點"],
            "output_format": "bullets",
            "include_project_sources": True,
            "source_id": "src_1",
            "result_limit": 5,
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["workflow_type"] == "web_search"
    assert payload["status"] == "completed"
    assert payload["final_web_result"]["title"] == "『包』Web Search 整理"
    assert [stage["stage_key"] for stage in payload["stages"]] == ["understand", "search", "filter", "ingest", "format"]
    assert payload["stages"][0]["agent_id"] == "main"
    assert payload["stages"][2]["agent_id"] == "organizer-agent"
    assert payload["stages"][3]["agent_id"] == "organizer-agent"
    assert payload["final_web_result"]["ingest_result"] is not None
    assert payload["final_ingest_result"] is not None
    assert any(event["message"] == "正在理解搜尋目標..." for event in payload["events"])
    assert any(event["message"] == "正在過濾無關資訊..." for event in payload["events"])
    assert any("寫入知識庫" in event["message"] or "入庫" in event["message"] for event in payload["events"])
    assert any(event["agent_id"] == "main" and "主控秘書" in event["message"] for event in payload["events"])

    list_response = client.get("/api/v1/workflows", params={"instanceId": instance_id, "workflowType": "web_search"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    continue_response = client.post(f"/api/v1/workflows/{payload['id']}/continue-to-report")
    assert continue_response.status_code == 201
    follow_up = continue_response.json()
    assert follow_up["workflow_type"] == "search_report"
    assert follow_up["status"] == "completed"
    assert follow_up["final_report"]["title"] == "『包』相關客服工作報告"
    assert follow_up["input_payload"]["continued_from_run_id"] == payload["id"]


def test_daily_news_config_and_news_brief_workflow(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    config_response = client.post(
        "/api/v1/openclaw/workflow-config",
        json={
            "instance_id": instance_id,
            "controller_agent_id": "main",
            "search_agent_id": "search-agent",
            "analysis_agent_id": "analysis-agent",
            "report_agent_id": "report-agent",
            "specialist_agents": {
                "search_web": {"agent_id": "main", "enabled": True},
                "organizer": {"agent_id": "organizer-agent", "enabled": True},
                "writer": {"agent_id": "report-agent", "enabled": True},
                "test_design": {"agent_id": "", "enabled": False},
                "ui_review": {"agent_id": "", "enabled": False},
                "monitor": {"agent_id": "", "enabled": False},
                "daily_news_brief": {"agent_id": "main", "enabled": True},
                "system_inspection": {"agent_id": "system-inspection-agent", "enabled": True},
            },
            "routing_rules": [],
            "handoff_policy": {
                "manual_review_required_on_conflict": True,
                "manual_review_required_on_high_risk": True,
                "max_search_retry_count": 1,
                "max_report_retry_count": 2,
                "timeout_escalation_seconds": 180,
                "fallback_mode": "controller",
            },
        },
    )
    assert config_response.status_code == 200

    news_config_response = client.post(
        "/api/v1/openclaw/daily-news-config",
        json={
            "instance_id": instance_id,
            "enabled": True,
            "brief_name": "AI Daily Brief",
            "topic": "AI 與半導體",
            "keywords": ["AI", "半導體"],
            "industries": ["半導體"],
            "regions": ["日本"],
            "people": [],
            "companies": ["NVIDIA"],
            "source_domains": ["reuters.com"],
            "source_urls": [],
            "must_include": ["AI"],
            "must_exclude": ["娛樂"],
            "focus_points": ["政策", "產品", "供應鏈"],
            "output_format": "bullets",
            "delivery_channel": "telegram",
            "telegram_target": "8351185582",
            "discord_channel_id": "",
            "schedule_timezone": "Asia/Tokyo",
            "schedule_time": "09:00",
        },
    )
    assert news_config_response.status_code == 200
    assert news_config_response.json()["data"]["brief_name"] == "AI Daily Brief"

    create_response = client.post("/api/v1/workflows/news-brief", json={"instance_id": instance_id})
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["workflow_type"] == "news_brief"
    assert payload["status"] == "completed"
    assert payload["final_news_brief"]["title"] == "每日新聞 Brief"
    assert [stage["stage_key"] for stage in payload["stages"]] == ["monitor", "search", "dedupe", "rank", "brief"]
    assert payload["final_news_brief"]["delivery_status"] in {"delivered", "failed"}

    get_config_response = client.get("/api/v1/openclaw/daily-news-config", params={"instanceId": instance_id})
    assert get_config_response.status_code == 200
    assert get_config_response.json()["data"]["topic"] == "AI 與半導體"

    list_response = client.get("/api/v1/workflows", params={"instanceId": instance_id, "workflowType": "news_brief"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_daily_news_prompts_are_compacted_for_downstream_stages() -> None:
    config = OpenClawDailyNewsConfigResponse(
        instance_id="oc_test",
        enabled=True,
        brief_name="Daily News Brief",
        topic="最新 agent 資訊",
        keywords=[],
        industries=[],
        regions=[],
        people=[],
        companies=[],
        source_domains=[],
        source_urls=[],
        must_include=[],
        must_exclude=[],
        focus_points=[],
        output_format="summary",
        delivery_channel="telegram",
        telegram_target="8351185582",
        discord_channel_id="",
        schedule_timezone="Asia/Tokyo",
        schedule_time="09:00",
        last_scheduled_date=None,
        last_run_id=None,
        last_delivery_status=None,
        last_delivery_error=None,
        created_at="2026-04-04T08:49:24.398919Z",
        updated_at="2026-04-04T08:49:24.398919Z",
    )
    monitor_prompt = _build_news_monitor_prompt(config)
    assert "last_delivery_error" not in monitor_prompt

    monitor_output = WorkflowNewsMonitorOutput(
        goal_summary="G" * 400,
        tracking_scope=["T" * 120] * 6,
        search_queries=[f"query-{index}-" + ("Q" * 120) for index in range(8)],
        watch_focus=["W" * 120] * 6,
    )
    search_prompt = _build_news_search_prompt(config, monitor_output)
    assert "last_delivery_error" not in search_prompt
    assert "query-4" not in search_prompt

    long_snippet = "A" * 1200
    search_output = WorkflowNewsSearchOutput(
        summary="S" * 800,
        raw_sources=[
            {
                "title": f"Story {index}",
                "snippet": long_snippet,
                "source_name": "Example Source",
                "reason": "R" * 400,
                "published_at": "2026-04-04",
                "url": f"https://example.com/{index}",
                "domain": "example.com",
            }
            for index in range(12)
        ],
    )
    dedupe_prompt = _build_news_dedupe_prompt(config, search_output)
    assert "Story 8" not in dedupe_prompt
    assert len(dedupe_prompt) < 7000


def test_daily_news_and_system_inspection_support_discord_delivery(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    client.post(
        "/api/v1/openclaw/workflow-config",
        json={
            "instance_id": instance_id,
            "controller_agent_id": "main",
            "search_agent_id": "search-agent",
            "analysis_agent_id": "analysis-agent",
            "report_agent_id": "report-agent",
            "specialist_agents": {
                "search_web": {"agent_id": "main", "enabled": True},
                "organizer": {"agent_id": "organizer-agent", "enabled": True},
                "writer": {"agent_id": "report-agent", "enabled": True},
                "test_design": {"agent_id": "", "enabled": False},
                "ui_review": {"agent_id": "", "enabled": False},
                "monitor": {"agent_id": "", "enabled": False},
                "daily_news_brief": {"agent_id": "main", "enabled": True},
                "system_inspection": {"agent_id": "system-inspection-agent", "enabled": True},
            },
            "routing_rules": [],
            "handoff_policy": {
                "manual_review_required_on_conflict": True,
                "manual_review_required_on_high_risk": True,
                "max_search_retry_count": 1,
                "max_report_retry_count": 2,
                "timeout_escalation_seconds": 180,
                "fallback_mode": "controller",
            },
        },
    )

    news_config_response = client.post(
        "/api/v1/openclaw/daily-news-config",
        json={
            "instance_id": instance_id,
            "enabled": True,
            "brief_name": "AI Daily Brief",
            "topic": "AI Agent",
            "keywords": [],
            "industries": [],
            "regions": [],
            "people": [],
            "companies": [],
            "source_domains": [],
            "source_urls": [],
            "must_include": [],
            "must_exclude": [],
            "focus_points": [],
            "output_format": "summary",
            "delivery_channel": "discord",
            "telegram_target": "",
            "discord_channel_id": "channel_daily_news",
            "schedule_timezone": "Asia/Tokyo",
            "schedule_time": "09:00",
        },
    )
    assert news_config_response.status_code == 200
    assert news_config_response.json()["data"]["delivery_channel"] == "discord"

    news_run = client.post("/api/v1/workflows/news-brief", json={"instance_id": instance_id})
    assert news_run.status_code == 201
    assert news_run.json()["final_news_brief"]["delivery_target"] == "channel_daily_news"

    inspection_config_response = client.post(
        "/api/v1/openclaw/system-inspection-config",
        json={
            "instance_id": instance_id,
            "enabled": True,
            "schedule_timezone": "Asia/Tokyo",
            "schedule_time": "09:30",
            "delivery_channel": "discord",
            "telegram_target": "",
            "discord_channel_id": "channel_system_inspection",
            "version_check_enabled": True,
            "log_review_enabled": True,
            "log_review_window_hours": 24,
            "log_review_limit": 500,
            "official_release_url": "https://docs.openclaw.ai/cli/agents",
        },
    )
    assert inspection_config_response.status_code == 200
    assert inspection_config_response.json()["data"]["delivery_channel"] == "discord"

    inspection_run = client.post("/api/v1/workflows/system-inspection", json={"instance_id": instance_id})
    assert inspection_run.status_code == 201
    assert inspection_run.json()["final_system_inspection"]["delivery_target"] == "channel_system_inspection"

    config = OpenClawDailyNewsConfigResponse.model_validate(news_config_response.json()["data"])
    search_output = WorkflowNewsSearchOutput(
        summary="S" * 800,
        raw_sources=[
            {
                "title": f"Story {index}",
                "snippet": "A" * 1200,
                "source_name": "Example Source",
                "reason": "R" * 400,
                "published_at": "2026-04-04",
                "url": f"https://example.com/{index}",
                "domain": "example.com",
            }
            for index in range(12)
        ],
    )

    dedupe_output = WorkflowNewsDedupeOutput(
        summary="D" * 700,
        unique_stories=[
            {
                "title": f"Unique {index}",
                "summary": "U" * 900,
                "importance_reason": "I" * 400,
                "possible_impact": "P" * 400,
                "sources": search_output.raw_sources[:4],
                "published_at": "2026-04-04",
                "background": "B" * 500,
                "watch_points": ["W" * 120] * 5,
                "event_key": f"event-{index}",
            }
            for index in range(10)
        ],
        removed_duplicates=4,
        dedupe_notes=["N" * 300] * 8,
    )
    rank_prompt = _build_news_rank_prompt(config, dedupe_output)
    assert "Unique 8" not in rank_prompt
    assert len(rank_prompt) < 12000

    rank_output = WorkflowNewsRankOutput(
        summary="R" * 700,
        top_stories=dedupe_output.unique_stories[:6],
        other_stories=dedupe_output.unique_stories[6:],
        trend_summary="T" * 500,
        watch_items=["W" * 200] * 8,
        uncertainties=["U" * 200] * 8,
    )
    brief_prompt = _build_news_brief_prompt(config, dedupe_output, rank_output)
    assert "Unique 9" not in brief_prompt
    assert len(brief_prompt) < 18000


def test_news_dedupe_timeout_uses_local_fallback() -> None:
    search_output = WorkflowNewsSearchOutput(
        summary="最新 AI Agent 相關新聞摘要",
        raw_sources=[
            {
                "title": "OpenClaw security issue deep dive",
                "snippet": "Ars Technica reports a new security concern and impact analysis.",
                "source_name": "Ars Technica",
                "reason": "最新且高相關的安全事件",
                "published_at": "2026-04-05",
                "url": "https://example.com/story-1",
                "domain": "example.com",
            },
            {
                "title": "OpenClaw security issue deep dive",
                "snippet": "Another coverage of the same issue from a second source.",
                "source_name": "The Neuron",
                "reason": "同一事件的後續跟進",
                "published_at": "2026-04-05",
                "url": "https://example.com/story-2",
                "domain": "example.com",
            },
        ],
    )

    fallback_output = _fallback_news_dedupe_output(search_output)

    assert fallback_output.summary.startswith("去重代理逾時")
    assert len(fallback_output.unique_stories) >= 1
    assert fallback_output.dedupe_notes
    assert fallback_output.removed_duplicates >= 1

    timeout_error = OpenClawServiceError(
        "OpenClaw agent 派發逾時。",
        detail="command=openclaw agent --agent daily-news-brief-agent timeout=180s",
        source_mode="cli",
    )
    assert _is_agent_timeout_error(timeout_error) is True


def test_system_inspection_config_and_workflow(client: TestClient) -> None:
    install_workflow_services()
    instance_id = create_instance(client)

    workflow_config_response = client.post(
        "/api/v1/openclaw/workflow-config",
        json={
            "instance_id": instance_id,
            "controller_agent_id": "main",
            "search_agent_id": "search-agent",
            "analysis_agent_id": "analysis-agent",
            "report_agent_id": "report-agent",
            "specialist_agents": {
                "search_web": {"agent_id": "main", "enabled": True},
                "organizer": {"agent_id": "organizer-agent", "enabled": True},
                "writer": {"agent_id": "report-agent", "enabled": True},
                "test_design": {"agent_id": "", "enabled": False},
                "ui_review": {"agent_id": "", "enabled": False},
                "monitor": {"agent_id": "", "enabled": False},
                "daily_news_brief": {"agent_id": "main", "enabled": True},
                "system_inspection": {"agent_id": "system-inspection-agent", "enabled": True},
            },
            "routing_rules": [],
            "handoff_policy": {
                "manual_review_required_on_conflict": True,
                "manual_review_required_on_high_risk": True,
                "max_search_retry_count": 1,
                "max_report_retry_count": 2,
                "timeout_escalation_seconds": 180,
                "fallback_mode": "controller",
            },
        },
    )
    assert workflow_config_response.status_code == 200

    config_response = client.post(
        "/api/v1/openclaw/system-inspection-config",
        json={
            "instance_id": instance_id,
            "enabled": True,
            "schedule_timezone": "Asia/Tokyo",
            "schedule_time": "09:30",
            "delivery_channel": "telegram",
            "telegram_target": "8351185582",
            "discord_channel_id": "",
            "version_check_enabled": True,
            "log_review_enabled": True,
            "log_review_window_hours": 24,
            "log_review_limit": 500,
            "official_release_url": "https://docs.openclaw.ai/cli/agents",
        },
    )
    assert config_response.status_code == 200
    assert config_response.json()["data"]["enabled"] is True

    create_response = client.post("/api/v1/workflows/system-inspection", json={"instance_id": instance_id})
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["workflow_type"] == "system_inspection"
    assert payload["status"] == "completed"
    assert [stage["stage_key"] for stage in payload["stages"]] == ["snapshot", "version_check", "log_review", "risk_assessment", "report"]
    assert payload["final_system_inspection"]["title"] == "系統巡檢與風險評估報告"
    assert payload["final_system_inspection"]["version_update_check"]["upgrade_recommendation"] == "test_before_upgrade"

    get_config_response = client.get("/api/v1/openclaw/system-inspection-config", params={"instanceId": instance_id})
    assert get_config_response.status_code == 200
    assert get_config_response.json()["data"]["official_release_url"] == "https://docs.openclaw.ai/cli/agents"

    list_response = client.get("/api/v1/workflows", params={"instanceId": instance_id, "workflowType": "system_inspection"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_system_report_prompt_is_compact() -> None:
    version_output = WorkflowSystemInspectionVersionOutput(
        current_version="OpenClaw 2026.4.1 (da64a97)",
        latest_version="2026.4.2",
        latest_version_status="available",
        version_gap="minor patch",
        release_summary=["R" * 400] * 8,
        compatibility_risks=["C" * 400] * 8,
        regression_test_checklist=["T" * 300] * 8,
        assumptions=["A" * 300] * 8,
        verification_steps=["V" * 300] * 8,
    )
    issue = WorkflowSystemInspectionLogIssue(
        issue_key="timeout_stage",
        category="timeout",
        description="D" * 500,
        frequency=10,
        severity="high",
        priority="p1",
        possible_root_causes=["R" * 200],
        affected_components=["workflow", "gateway", "telegram", "plugin", "ui"],
        impact_scope="I" * 300,
        fix_actions=["F" * 200] * 4,
        optimization_actions=["O" * 200] * 4,
        assumptions=["A" * 200] * 4,
        verification_steps=["V" * 200] * 4,
    )
    log_review_output = WorkflowSystemInspectionLogReviewOutput(
        summary="S" * 500,
        issues=[issue] * 8,
        log_window_hours=24,
        inspected_log_count=500,
    )
    risk_output = WorkflowSystemInspectionRiskOutput(
        summary="R" * 500,
        upgrade_recommendation="do_not_upgrade_yet",
        high_priority_risks=[issue] * 8,
        immediate_actions=["I" * 200] * 8,
        assumptions=["A" * 200] * 8,
        verification_steps=["V" * 200] * 8,
    )
    prompt = _build_system_report_prompt(
        _compact_system_version_output(version_output),
        _compact_system_log_review_output(log_review_output),
        _compact_system_risk_output(risk_output),
    )
    assert len(prompt) < 14000
    assert '"version_update_check"' not in prompt
