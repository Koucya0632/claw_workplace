import { PixelCard } from "@/components/pixel-card";
import { StatusPill } from "@/components/status-pill";
import { cn } from "@/lib/utils";

interface RoleState {
  name: string;
  tagline: string;
  status: string;
  quote: string;
}

interface RoleSquadProps {
  roles: RoleState[];
  mode?: "full" | "summary" | "collapsible";
  defaultOpen?: boolean;
}

export function RoleSquad({
  roles,
  mode = "full",
  defaultOpen = false
}: RoleSquadProps) {
  if (mode === "summary") {
    return (
      <PixelCard title="參與角色" eyebrow="Crew" variant="muted" density="compact">
        <div className="grid gap-2 md:grid-cols-2">
          {roles.map((role) => (
            <article
              key={role.name}
              className={cn(
                "rounded-[1rem] border border-slate-200 bg-white/80 px-4 py-3",
                role.status === "failed" && "border-coral/30 bg-coral/10",
                role.status === "running" && "border-gold/30 bg-gold/10"
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-black tracking-[0.05em] text-ink">{role.name}</h3>
                </div>
                <StatusPill status={role.status} />
              </div>
            </article>
          ))}
        </div>
      </PixelCard>
    );
  }

  if (mode === "collapsible") {
    return (
      <PixelCard title="參與角色" eyebrow="Crew" variant="muted" density="compact">
        <details open={defaultOpen} className="group">
          <summary className="cursor-pointer list-none text-sm font-black tracking-[0.05em] text-ink">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>{summarizeRoles(roles)}</span>
              <span className="text-xs uppercase tracking-[0.16em] text-slate-500 group-open:hidden">展開</span>
              <span className="hidden text-xs uppercase tracking-[0.16em] text-slate-500 group-open:inline">收合</span>
            </div>
          </summary>
          <div className="mt-4 space-y-2">{renderRoleArticles(roles, false)}</div>
        </details>
      </PixelCard>
    );
  }

  return (
    <PixelCard title="角色小隊" eyebrow="Crew" variant="muted">
      <div className="space-y-2">{renderRoleArticles(roles, true)}</div>
    </PixelCard>
  );
}

function renderRoleArticles(roles: RoleState[], showTagline: boolean) {
  return roles.map((role) => (
    <article
      key={role.name}
      className={cn(
        "rounded-[1rem] border px-4 py-3",
        role.status === "completed" && "border-mint/40 bg-mint/50",
        role.status === "running" && "border-gold/40 bg-gold/20",
        role.status === "failed" && "border-coral/35 bg-coral/12",
        (role.status === "disabled" || role.status === "upcoming") && "border-slate-200 bg-white/70",
        !["completed", "running", "failed", "disabled", "upcoming"].includes(role.status) &&
          "border-slate-200 bg-white/80"
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-black tracking-[0.05em] text-ink">{role.name}</h3>
          {showTagline ? <p className="text-xs text-slate-600">{role.tagline}</p> : null}
        </div>
        <StatusPill status={role.status} />
      </div>
    </article>
  ));
}

function summarizeRoles(roles: RoleState[]) {
  const activeCount = roles.filter((role) => role.status === "running" || role.status === "active").length;
  const readyCount = roles.filter((role) => role.status === "ready" || role.status === "completed").length;
  return `${roles.length} 個角色，${activeCount} 個進行中，${readyCount} 個待命或已完成`;
}
