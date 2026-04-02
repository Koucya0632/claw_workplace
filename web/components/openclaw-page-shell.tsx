import type { ReactNode } from "react";

import { OpenClawConsoleNav } from "@/components/openclaw-console-nav";
import { PixelCard } from "@/components/pixel-card";
import { RoleSquad } from "@/components/role-squad";

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
  children: ReactNode;
}

export function OpenClawPageShell({ title, description, roles, children }: OpenClawPageShellProps) {
  // OpenClaw 管理頁延續既有工作台骨架，避免新區域突然跳出不同產品語言。
  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <RoleSquad roles={roles} />

      <section className="space-y-5">
        <PixelCard title={title} eyebrow="OpenClaw Console">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-slate-700">{description}</p>
            <OpenClawConsoleNav />
          </div>
        </PixelCard>
        {children}
      </section>
    </div>
  );
}
