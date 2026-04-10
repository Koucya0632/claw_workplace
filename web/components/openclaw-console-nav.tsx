"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const CONTROL_CENTER_ITEMS = [
  { href: "/openclaw", label: "Overview", blurb: "Global status, burn, and next operator move." },
  { href: "/openclaw/usage", label: "Usage", blurb: "Budget windows, subscription posture, and connector gaps." },
  { href: "/openclaw/staff", label: "Staff", blurb: "Live sessions, queue posture, and current crew presence." },
  { href: "/openclaw/collaboration", label: "Collaboration", blurb: "Shared threads, recent discussion, and review tempo." },
  { href: "/openclaw/hall", label: "Hall", blurb: "Three-pane hall for task threads, chat, and context." },
  { href: "/openclaw/tasks", label: "Tasks", blurb: "Workbench for tracked execution, rooms, and runtime evidence." },
  { href: "/openclaw/docs", label: "Documents", blurb: "Workspace files and shared reference surface." },
  { href: "/openclaw/memory", label: "Memory", blurb: "Agent memory files, visibility, and maintenance scope." },
  { href: "/openclaw/settings", label: "Settings", blurb: "Safety defaults, diagnostics, and connection completeness." }
] as const;

const ADMIN_ITEMS = [
  { href: "/openclaw/instances", label: "實例", blurb: "Gateway, token, and instance health management." },
  { href: "/openclaw/agents", label: "Agents", blurb: "Roster, capability, hook, and routing management." },
  { href: "/openclaw/workflow", label: "Workflow", blurb: "Controller, specialist mapping, and handoff policy." },
  { href: "/openclaw/development", label: "Development", blurb: "Engineering execution workflow and structured delivery." },
  { href: "/openclaw/knowledge", label: "Knowledge", blurb: "Ingestion history, versions, and source governance." },
  { href: "/openclaw/daily-news", label: "Daily News", blurb: "Recurring news workflow, sources, and delivery targets." },
  { href: "/openclaw/system-inspection", label: "Inspection", blurb: "Version checks, risk scoring, and report routing." },
  { href: "/openclaw/devices", label: "Devices", blurb: "Device runtime, actions, and wiring availability." },
  { href: "/openclaw/config", label: "Config", blurb: "Instance config, defaults, and repo-facing settings." },
  { href: "/openclaw/logs", label: "Logs", blurb: "Gateway logs, snapshots, and operator drill-down." },
  { href: "/openclaw/actions", label: "Actions", blurb: "Hooks, wake calls, and audited manual dispatch." }
] as const;

export function OpenClawConsoleNav() {
  // 導覽改成 reference 風格的左 rail section links，而不是按鈕群。
  const pathname = usePathname();

  return (
    <div className="space-y-4">
      <NavSection label="Control Center" items={CONTROL_CENTER_ITEMS} pathname={pathname} />
      <NavSection label="Admin Tools" items={ADMIN_ITEMS} pathname={pathname} />
    </div>
  );
}

function NavSection({
  label,
  items,
  pathname
}: {
  label: string;
  items: ReadonlyArray<{ href: string; label: string; blurb: string }>;
  pathname: string;
}) {
  return (
    <section className="space-y-2">
      <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">{label}</p>
      <div className="space-y-1 rounded-[1.25rem] border border-slate-200 bg-white/55 p-2">
        {items.map((item) => {
          const active = item.href === "/openclaw" ? pathname === item.href : pathname.startsWith(item.href);

          return (
            <div key={item.href} className="rounded-[1rem]">
              <Link
                href={item.href}
                className={cn(
                  "flex items-center justify-between gap-3 rounded-[1rem] px-3 py-2.5 transition-colors",
                  active ? "bg-ink text-sand" : "text-ink hover:bg-sand/70"
                )}
              >
                <div className="min-w-0">
                  <p className="text-sm font-black tracking-[0.05em]">{item.label}</p>
                </div>
                <span
                  className={cn(
                    "mt-0.5 shrink-0 text-[10px] font-black uppercase tracking-[0.18em]",
                    active ? "text-sand" : "text-slate-400"
                  )}
                >
                  {active ? "Live" : "Open"}
                </span>
              </Link>
              {active ? <p className="px-3 pb-2 pt-1 text-xs leading-5 text-slate-600">{item.blurb}</p> : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
