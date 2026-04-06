import { StatusPill } from "@/components/status-pill";

const SOURCE_STATUS_LABELS: Record<string, string> = {
  active: "運行中",
  disabled: "已停用",
  ready: "已就緒",
  scanning: "掃描中"
};

const SOURCE_SYNC_LABELS: Record<string, string> = {
  healthy: "正常",
  warning: "警告",
  failed: "異常",
  syncing: "同步中",
  never_scanned: "未同步"
};

function prettifyStatus(status: string, labels: Record<string, string>) {
  return labels[status] ?? status.replaceAll("_", " ");
}

export function SourceStatusBadge({ status }: { status: string }) {
  return <StatusPill status={status} label={prettifyStatus(status, SOURCE_STATUS_LABELS)} />;
}

export function SourceSyncBadge({ status }: { status: string }) {
  return <StatusPill status={status} label={prettifyStatus(status, SOURCE_SYNC_LABELS)} />;
}
