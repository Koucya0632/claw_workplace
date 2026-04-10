import type { ReactNode } from "react";

import { OpenClawConsoleNav } from "@/components/openclaw-console-nav";
import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";
import { cn } from "@/lib/utils";

interface OpenClawRole {
  name: string;
  tagline: string;
  status: string;
  quote: string;
}

interface OpenClawPageShellProps {
  title: string;
  description: string;
  roles: OpenClawRole[];
  sectionGroup?: "Control Center" | "Admin Tools";
  sectionLabel?: string;
  summary?: ReactNode;
  headerActions?: ReactNode;
  inspector?: ReactNode;
  sidebarMode?: "compact" | "hidden";
  roleMode?: "full" | "summary" | "collapsible";
  minimalHeader?: boolean;
  childrenClassName?: string;
  children: ReactNode;
}

export function OpenClawPageShell({
  title,
  description,
  roles,
  sectionGroup = "Control Center",
  sectionLabel,
  summary,
  headerActions,
  inspector,
  sidebarMode = "compact",
  roleMode = "summary",
  minimalHeader = true,
  childrenClassName,
  children
}: OpenClawPageShellProps) {
  const effectiveSectionLabel = sectionLabel ?? title;
  const activeRoleCount = roles.filter((role) => role.status === "running" || role.status === "active").length;

  return (
    <div
      className={cn(
        "grid gap-5",
        sidebarMode === "compact" ? "xl:grid-cols-[280px_minmax(0,1fr)]" : undefined
      )}
    >
      {sidebarMode === "compact" ? (
        <aside className="order-2 space-y-4 xl:order-1 xl:sticky xl:top-5 xl:max-h-[calc(100vh-2.5rem)] xl:self-start xl:overflow-y-auto xl:pr-2">
          <PixelCard title="OpenClaw" eyebrow="Navigation" variant="muted" density="compact">
            <OpenClawConsoleNav />
          </PixelCard>
          <RoleSquad roles={roles} mode={roleMode} />
        </aside>
      ) : null}

      <section className={cn("order-1 space-y-5", sidebarMode === "compact" ? "xl:order-2" : undefined)}>
        <header className="page-intro rounded-[1.75rem] px-5 py-5 md:px-6">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-4xl space-y-3">
                <p className="text-[10px] uppercase tracking-[0.28em] text-slate-600">{sectionGroup}</p>
                <div className="space-y-2">
                  <h1 className="pixel-title text-2xl leading-9 font-black tracking-[0.06em] text-ink md:text-3xl">
                    {title}
                  </h1>
                  <p className={cn("max-w-3xl text-slate-700", minimalHeader ? "text-sm leading-6" : "text-sm leading-7")}>
                    {description}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 xl:max-w-sm xl:justify-end">
                <HeaderChip label="Section" value={effectiveSectionLabel} />
                <HeaderChip label="Crew" value={`${roles.length} roles / ${activeRoleCount} active`} />
                <HeaderChip label="Workspace" value="OpenClaw" />
              </div>
            </div>
            {summary || headerActions ? (
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
                <div>{summary}</div>
                {headerActions ? <div className="lg:justify-self-end">{headerActions}</div> : null}
              </div>
            ) : null}
          </div>
        </header>

        <div className={cn("space-y-5", childrenClassName)}>{children}</div>

        {inspector ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">Support Details</p>
                <h2 className="pixel-title mt-1 text-xl font-black tracking-[0.05em] text-ink">Operational controls</h2>
              </div>
            </div>
            <div className="grid gap-5 lg:grid-cols-2">{inspector}</div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function HeaderChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white/84 px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.12em] text-ink">
      <span className="text-slate-500">{label}</span>
      <span>{value}</span>
    </span>
  );
}
