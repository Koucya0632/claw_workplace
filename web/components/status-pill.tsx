import { cn } from "@/lib/utils";

interface StatusPillProps {
  status: string;
  label?: string;
}

const COLOR_MAP: Record<string, string> = {
  active: "bg-sky-100 text-sky-900",
  ready: "bg-mint text-ink",
  running: "bg-gold text-ink",
  completed: "bg-teal text-white",
  success: "bg-teal text-white",
  healthy: "bg-mint text-ink",
  warning: "bg-amber-200 text-amber-950",
  failed: "bg-coral text-white",
  scanning: "bg-gold text-ink",
  syncing: "bg-gold text-ink",
  never_scanned: "bg-slate-100 text-slate-600",
  pending: "bg-slate-200 text-slate-700",
  unknown: "bg-slate-100 text-slate-600",
  upcoming: "bg-slate-100 text-slate-500",
  disabled: "bg-slate-100 text-slate-500"
};

export function StatusPill({ status, label }: StatusPillProps) {
  // 狀態標籤在多個面板都會重用，因此顏色映射統一放在元件內。
  return (
    <span
      className={cn(
        "inline-flex border-2 border-ink px-2 py-1 text-[10px] font-black uppercase tracking-[0.2em]",
        COLOR_MAP[status] ?? "bg-slate-100 text-slate-600"
      )}
    >
      {label ?? status}
    </span>
  );
}
