import React from "react";

import { fireEvent, render, screen } from "@testing-library/react";

import { WorkflowStageBoard } from "@/components/workflow-stage-board";
import type { WorkflowRunResponse } from "@/lib/types";


describe("WorkflowStageBoard", () => {
  it("keeps payload details collapsed until requested", () => {
    const run: WorkflowRunResponse = {
      id: "run_1",
      instance_id: "instance_1",
      workflow_type: "development_execution",
      status: "failed",
      current_stage: "implementation",
      active_agent_id: "fullstack-engineer-agent",
      overall_progress_percent: 66,
      input_payload: {},
      error_message:
        "summary=已完成 sources page 的主骨架與管理操作。 / completed=新增 KPI 摘要卡；補齊來源管理表格 / modules=web/app/settings/sources/page.tsx；api/app/routers/sources.py / provider=minimax / model=MiniMax-M2.7 / text_fields=none",
      stages: [
        {
          id: "stage_implementation",
          stage_key: "implementation",
          agent_id: "fullstack-engineer-agent",
          status: "failed",
          progress_percent: 100,
          input_payload: {},
          output_payload: null,
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
      ],
      events: [
        {
          id: "event_implementation",
          run_id: "run_1",
          stage_key: "implementation",
          agent_id: "fullstack-engineer-agent",
          status: "failed",
          progress_percent: 100,
          message: "implementation 階段失敗。",
          payload: {
            error:
              "summary=已完成 sources page 的主骨架與管理操作。 / completed=新增 KPI 摘要卡；補齊來源管理表格 / modules=web/app/settings/sources/page.tsx；api/app/routers/sources.py / provider=minimax / model=MiniMax-M2.7 / text_fields=none"
          },
          created_at: new Date().toISOString(),
        }
      ],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(<WorkflowStageBoard run={run} />);

    const details = screen.getByText("查看詳情").closest("details");
    expect(details).not.toHaveAttribute("open");

    fireEvent.click(screen.getByText("查看詳情"));
    expect(details).toHaveAttribute("open");

    expect(screen.getAllByText("已完成 sources page 的主骨架與管理操作。 (provider minimax / model MiniMax-M2.7)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("- 新增 KPI 摘要卡").length).toBeGreaterThan(0);
    expect(screen.getAllByText("關聯模組：web/app/settings/sources/page.tsx、api/app/routers/sources.py").length).toBeGreaterThan(0);
  });
});
