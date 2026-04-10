import React from "react";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import SearchPage from "@/app/search/page";
import * as api from "@/lib/api";

const replaceMock = vi.fn();

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams("")
}));

vi.mock("@/lib/api", () => ({
  continueWorkflowToReport: vi.fn(),
  createSearchReportWorkflow: vi.fn(),
  createWebSearchWorkflow: vi.fn(),
  fetchOpenClawInstances: vi.fn(),
  fetchSources: vi.fn(),
  fetchWorkflowRun: vi.fn(),
  fetchWorkflowRuns: vi.fn()
}));

describe("SearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchSources).mockResolvedValue([
      {
        id: "src_1",
        name: "Product Docs",
        type: "local",
        status: "healthy",
        is_enabled: true,
        config: { path: "/docs" },
        document_count: 4,
        last_sync_status: "healthy",
        last_sync_error: null,
        last_successful_sync_at: new Date().toISOString(),
        last_failed_sync_at: null,
        last_sync_result: {
          scanned_count: 4,
          skipped_count: 0,
          error_count: 0
        },
        last_scan_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue([
      {
        id: "oc_1",
        name: "Primary Gateway",
        gateway_url: "http://gateway.internal",
        is_active: true,
        has_token: true,
        last_health_status: "healthy",
        last_health_checked_at: new Date().toISOString(),
        snapshot_summary: {
          health_status: "healthy",
          agent_count: 3,
          device_count: 1,
          config_updated_at: new Date().toISOString()
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]);
    vi.mocked(api.fetchWorkflowRuns).mockResolvedValue([]);
    vi.mocked(api.fetchWorkflowRun).mockResolvedValue({
      id: "run_1",
      instance_id: "oc_1",
      workflow_type: "search_report",
      status: "completed",
      current_stage: "report",
      active_agent_id: "report-agent",
      overall_progress_percent: 100,
      input_payload: {},
      stages: [],
      events: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
  });

  it("keeps the core workflow controls in the first screen", async () => {
    render(<SearchPage />);

    expect(await screen.findByRole("heading", { name: "搜索工作台" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("輸入查詢")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "啟動流程" })).toBeInTheDocument();
    });
    expect(screen.getByText("流程階段")).toBeInTheDocument();
    expect(screen.getByText("歷史流程")).toBeInTheDocument();
    expect(screen.getByText("處理鏈路")).toBeInTheDocument();
    expect(screen.getByText("最終結果")).toBeInTheDocument();
  });

  it("keeps web search advanced filters collapsed until expanded", async () => {
    render(<SearchPage />);

    await screen.findByRole("heading", { name: "搜索工作台" });
    fireEvent.click(screen.getByRole("button", { name: /Web Search \+ Ingest/ }));

    const advancedFilters = screen.getByTestId("workflow-advanced-filters");
    expect(advancedFilters).not.toHaveAttribute("open");

    fireEvent.click(within(advancedFilters).getByText("進階條件"));

    await waitFor(() => {
      expect(advancedFilters).toHaveAttribute("open");
    });
  });
});
