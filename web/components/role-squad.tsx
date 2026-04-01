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
}

export function RoleSquad({ roles }: RoleSquadProps) {
  // 左側角色小隊是產品核心辨識點，因此用固定卡片節奏表現。
  return (
    <PixelCard title="角色小隊" eyebrow="Crew">
      <div className="space-y-3">
        {roles.map((role) => (
          <article
            key={role.name}
            className={cn(
              "border-4 border-ink p-3",
              role.status === "completed" && "bg-mint/70",
              role.status === "running" && "bg-gold/60",
              role.status === "failed" && "bg-coral/80 text-white",
              (role.status === "disabled" || role.status === "upcoming") && "bg-slate-100"
            )}
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-black tracking-[0.08em]">{role.name}</h3>
                <p className="text-xs text-slate-600">{role.tagline}</p>
              </div>
              <StatusPill status={role.status} />
            </div>
            <p className="text-xs leading-6">{role.quote}</p>
          </article>
        ))}
      </div>
    </PixelCard>
  );
}

