import React from "react";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import OpenClawActionsPage from "@/app/openclaw/actions/page";
import OpenClawAgentsPage from "@/app/openclaw/agents/page";
import OpenClawDevicesPage from "@/app/openclaw/devices/page";
import OpenClawOverviewPage from "@/app/openclaw/page";
import * as api from "@/lib/api";

let mockPathname = "/openclaw";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname
}));

vi.mock("@/lib/api", () => ({
  fetchOpenClawInstances: vi.fn(),
  fetchOpenClawOperations: vi.fn(),
  fetchOpenClawAgents: vi.fn(),
  fetchOpenClawDevices: vi.fn(),
  updateOpenClawAgentSearchCapability: vi.fn(),
  runOpenClawDeviceAction: vi.fn(),
  dispatchOpenClawAgentHook: vi.fn(),
  dispatchOpenClawWakeHook: vi.fn(),
  createOpenClawAgent: vi.fn()
}));

const INSTANCE_FIXTURE = [
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
      agent_count: 2,
      device_count: 1,
      config_updated_at: new Date().toISOString()
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

describe("OpenClaw pages", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading then empty state on overview page", async () => {
    mockPathname = "/openclaw";

    let resolveInstances: ((value: typeof INSTANCE_FIXTURE | []) => void) | undefined;
    let resolveOperations: ((value: []) => void) | undefined;

    vi.mocked(api.fetchOpenClawInstances).mockReturnValue(
      new Promise((resolve) => {
        resolveInstances = resolve;
      })
    );
    vi.mocked(api.fetchOpenClawOperations).mockReturnValue(
      new Promise((resolve) => {
        resolveOperations = resolve;
      })
    );

    render(<OpenClawOverviewPage />);

    expect(screen.getByText("正在同步 OpenClaw 狀態...")).toBeInTheDocument();

    resolveInstances?.([]);
    resolveOperations?.([]);

    await waitFor(() => {
      expect(screen.getByText("尚未建立 OpenClaw Instance，請先前往實例頁新增。")).toBeInTheDocument();
    });
  });

  it("shows error state on overview page when API fails", async () => {
    mockPathname = "/openclaw";
    vi.mocked(api.fetchOpenClawInstances).mockRejectedValue(new Error("overview failed"));
    vi.mocked(api.fetchOpenClawOperations).mockResolvedValue([]);

    render(<OpenClawOverviewPage />);

    await waitFor(() => {
      expect(screen.getByText("overview failed")).toBeInTheDocument();
    });
  });

  it("locks only the clicked device action button while action is pending", async () => {
    mockPathname = "/openclaw/devices";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevices).mockResolvedValue([
      {
        id: "device_pending",
        name: "Alice iPhone",
        status: "pending",
        platform: "ios",
        pending_action: "approve",
        metadata: {}
      }
    ]);

    let resolveAction: (() => void) | undefined;
    vi.mocked(api.runOpenClawDeviceAction).mockReturnValue(
      new Promise((resolve) => {
        resolveAction = () => resolve({});
      })
    );

    render(<OpenClawDevicesPage />);

    const approveButton = await screen.findByRole("button", { name: "approve" });
    fireEvent.click(approveButton);

    expect(screen.getByRole("button", { name: "approve 中..." })).toBeDisabled();

    resolveAction?.();

    await waitFor(() => {
      expect(screen.getByText("Device approve 已完成。")).toBeInTheDocument();
    });
  });

  it("renders paired devices returned by the API", async () => {
    mockPathname = "/openclaw/devices";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawDevices).mockResolvedValue([
      {
        id: "device_paired",
        name: "Unknown Device",
        status: "paired",
        platform: "darwin",
        pending_action: null,
        metadata: {
          clientId: "openclaw-control-ui"
        }
      }
    ]);

    render(<OpenClawDevicesPage />);

    expect(await screen.findByText("Unknown Device")).toBeInTheDocument();
    expect(screen.getByText("darwin")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "revoke" })).toBeInTheDocument();
  });

  it("toggles agent search capability from the agents page", async () => {
    mockPathname = "/openclaw/agents";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.fetchOpenClawAgents)
      .mockResolvedValueOnce([
        {
          id: "support-agent",
          name: "Support Agent",
          status: "ready",
          channel_count: 0,
          metadata: {
            capabilities: {
              search_api: {
                enabled: false,
                plugin_ready: false,
                plugin_enabled: false,
                bridge_ready: false
              }
            }
          }
        }
      ])
      .mockResolvedValueOnce([
        {
          id: "support-agent",
          name: "Support Agent",
          status: "ready",
          channel_count: 0,
          metadata: {
            capabilities: {
              search_api: {
                enabled: false,
                plugin_ready: false,
                plugin_enabled: false,
                bridge_ready: false
              }
            }
          }
        }
      ])
      .mockResolvedValueOnce([
        {
          id: "support-agent",
          name: "Support Agent",
          status: "ready",
          channel_count: 0,
          metadata: {
            capabilities: {
              search_api: {
                enabled: true,
                plugin_ready: true,
                plugin_enabled: true,
                bridge_ready: true,
                plugin_id: "project-search",
                last_sync_message: "原生搜索工具已就緒"
              }
            }
          }
        }
      ]);
    vi.mocked(api.updateOpenClawAgentSearchCapability).mockResolvedValue({
      id: "cap_1",
      instance_id: "oc_1",
      agent_id: "support-agent",
      capability_key: "search_api",
      is_enabled: true,
      config: {},
      native_plugin_id: "project-search",
      native_plugin_ready: true,
      native_plugin_enabled: true,
      bridge_ready: true,
      last_sync_status: "success",
      last_sync_message: "原生搜索工具已就緒",
      workspace_synced: false,
      message: "原生搜索工具已就緒",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });

    render(<OpenClawAgentsPage />);

    const toggleButton = await screen.findByRole("button", { name: "啟用搜索能力" });
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(screen.getByText("原生搜索工具已就緒")).toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: "停用搜索能力" })).toBeInTheDocument();
    expect(screen.getByText("project-search", { exact: false })).toBeInTheDocument();
  });

  it("shows agent success and disabled wake state on actions page", async () => {
    mockPathname = "/openclaw/actions";
    vi.mocked(api.fetchOpenClawInstances).mockResolvedValue(INSTANCE_FIXTURE);
    vi.mocked(api.dispatchOpenClawAgentHook).mockResolvedValue({ accepted: true });

    render(<OpenClawActionsPage />);

    const agentButton = await screen.findByRole("button", { name: "送出 Agent Hook" });
    fireEvent.click(agentButton);

    await waitFor(() => {
      expect(screen.getByText(/Agent Hook 派發完成/)).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Wake Hook 目前未開放" })).toBeDisabled();
    expect(
      screen.getByText("目前這個 OpenClaw 版本沒有穩定可用的 wake 派發入口。若要測試任務派發，請先使用左側的 Agent Hook。")
    ).toBeInTheDocument();
  });
});
