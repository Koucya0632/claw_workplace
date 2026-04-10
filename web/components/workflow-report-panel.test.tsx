import React from "react";

import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { WorkflowReportPanel } from "@/components/workflow-report-panel";
import type { WorkflowRunResponse } from "@/lib/types";


vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>
}));

describe("WorkflowReportPanel", () => {
  it("shows development delivery status on completed runs", () => {
    const run: WorkflowRunResponse = {
      id: "run_1",
      instance_id: "oc_1",
      workflow_type: "development_execution",
      status: "completed",
      current_stage: "handoff",
      active_agent_id: "main",
      overall_progress_percent: 100,
      input_payload: {},
      final_development_report: {
        task_name: "優化資料源頁面",
        problem_definition: "資料源頁缺少整體可視化與高效率管理能力。",
        requirements_analysis: ["需要 KPI 摘要"],
        solution_design: ["採 Dashboard + Table + Drawer 架構"],
        technology_selection: [],
        task_breakdown_schedule: [],
        development_results: ["資料源頁改為 dashboard 型式"],
        test_results: ["vitest passed"],
        risks_and_todos: ["後續可加入趨勢圖與批次操作"],
        final_summary: "工程任務已完成。",
        delivery_status: "delivered",
        delivery_target: "channel_development",
        delivery_error: null,
        delivery_source: "runtime_route",
        delivery_reason: "未找到 Development 專屬設定，已回退使用 Discord #develop route（channel_development）。",
      },
      error_message: null,
      stages: [],
      events: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(<WorkflowReportPanel run={run} />);

    expect(screen.getByText("Discord 匯報")).toBeInTheDocument();
    expect(screen.getByText("狀態：delivered")).toBeInTheDocument();
    expect(screen.getByText("目標：channel_development")).toBeInTheDocument();
    expect(screen.getByText("來源：runtime_route")).toBeInTheDocument();
    expect(screen.getByText("說明：未找到 Development 專屬設定，已回退使用 Discord #develop route（channel_development）。")).toBeInTheDocument();
  });

  it("shows development delivery status on failed runs from workflow events", () => {
    const run: WorkflowRunResponse = {
      id: "run_2",
      instance_id: "oc_1",
      workflow_type: "development_execution",
      status: "failed",
      current_stage: "implementation",
      active_agent_id: "fullstack-engineer-agent",
      overall_progress_percent: 75,
      input_payload: { task_name: "修復 sources 同步" },
      error_message: "summary=已完成 sources page 的主骨架與管理操作。 / provider=minimax / model=MiniMax-M2.7",
      stages: [],
      events: [
        {
          id: "event_delivery_failed",
          run_id: "run_2",
          stage_key: "implementation",
          agent_id: "main",
          status: "failed",
          progress_percent: 75,
          message: "Development 失敗後嘗試推送 Discord 摘要，但發送失敗。",
          payload: {
            delivery_status: "failed",
            delivery_target: "channel_development",
            delivery_error: "discord send failed",
            delivery_source: "runtime_route",
            delivery_reason: "未找到 Development 專屬設定，已回退使用 Discord #develop route（channel_development）。",
          },
          created_at: new Date().toISOString(),
        }
      ],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(<WorkflowReportPanel run={run} />);

    expect(screen.getByText("執行異常摘要")).toBeInTheDocument();
    expect(screen.getByText("Discord 匯報狀態：failed")).toBeInTheDocument();
    expect(screen.getByText("目標：channel_development")).toBeInTheDocument();
    expect(screen.getByText("來源：runtime_route")).toBeInTheDocument();
    expect(screen.getByText("說明：未找到 Development 專屬設定，已回退使用 Discord #develop route（channel_development）。")).toBeInTheDocument();
    expect(screen.getByText("錯誤：discord send failed")).toBeInTheDocument();
  });
});
