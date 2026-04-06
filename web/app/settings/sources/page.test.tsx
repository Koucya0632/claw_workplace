import React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import SourceSettingsPage from "@/app/settings/sources/page";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  fetchSources: vi.fn(),
  fetchSourceMetrics: vi.fn(),
  fetchSourceDetail: vi.fn(),
  createSource: vi.fn(),
  updateSource: vi.fn(),
  scanSource: vi.fn(),
  enableSource: vi.fn(),
  disableSource: vi.fn(),
  deleteSource: vi.fn()
}));

const SOURCE_FIXTURE = [
  {
    id: "src_1",
    name: "OpenClaw 官網",
    type: "web_page" as const,
    status: "active",
    is_enabled: true,
    config: { url: "https://docs.openclaw.ai" },
    document_count: 12,
    last_sync_status: "healthy",
    last_sync_error: null,
    last_successful_sync_at: new Date().toISOString(),
    last_failed_sync_at: null,
    last_sync_result: {
      scanned_count: 12,
      skipped_count: 0,
      error_count: 0
    },
    last_scan_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

describe("SourceSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchSources).mockResolvedValue(SOURCE_FIXTURE);
    vi.mocked(api.fetchSourceMetrics).mockResolvedValue({
      total_sources: 1,
      healthy_sources: 1,
      warning_sources: 0,
      failed_sources: 0,
      syncing_sources: 0,
      disabled_sources: 0,
      recently_updated_sources: 1,
      recent_sync_failures: 0
    });
  });

  it("renders metrics and table rows", async () => {
    render(<SourceSettingsPage />);

    expect(await screen.findByText("資料源總覽")).toBeInTheDocument();
    expect(screen.getByText("OpenClaw 官網")).toBeInTheDocument();
    expect(screen.getByText("資料源總表")).toBeInTheDocument();
  });

  it("opens create dialog from toolbar", async () => {
    render(<SourceSettingsPage />);

    await screen.findByText("OpenClaw 官網");
    fireEvent.click(screen.getByRole("button", { name: "新增資料源" }));

    await waitFor(() => {
      expect(screen.getByText("Source Form")).toBeInTheDocument();
    });
  });
});
