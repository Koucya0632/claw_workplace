"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

type StaffRoleKey = "manager" | "planner" | "coder" | "reviewer" | "generalist" | "unassigned";

interface StaffRoleLottieProps {
  roleKey: StaffRoleKey;
  statusLabel: string;
  className?: string;
}

const ROLE_THEME: Record<
  StaffRoleKey,
  {
    chip: string;
    frame: string;
    accent: string;
    label: string;
  }
> = {
  manager: {
    chip: "Manager view",
    frame: "border-coral bg-coral/10",
    accent: "text-coral",
    label: "Global pacing"
  },
  planner: {
    chip: "Planner view",
    frame: "border-gold bg-gold/15",
    accent: "text-amber-700",
    label: "Research rhythm"
  },
  coder: {
    chip: "Coder view",
    frame: "border-teal bg-teal/10",
    accent: "text-teal-700",
    label: "Build stream"
  },
  reviewer: {
    chip: "Reviewer view",
    frame: "border-mint bg-mint/40",
    accent: "text-emerald-700",
    label: "Risk scan"
  },
  generalist: {
    chip: "Generalist view",
    frame: "border-slate-400 bg-slate-100",
    accent: "text-slate-700",
    label: "Flexible lane"
  },
  unassigned: {
    chip: "Unassigned view",
    frame: "border-slate-300 bg-slate-100/80",
    accent: "text-slate-500",
    label: "Pending role"
  }
};

function isActiveStatus(statusLabel: string) {
  return /running|active|working|工作中|執行中|处理中|處理中/i.test(statusLabel);
}

export function StaffRoleLottie({ roleKey, statusLabel, className }: StaffRoleLottieProps) {
  const [reducedMotion, setReducedMotion] = useState(false);
  const theme = ROLE_THEME[roleKey] ?? ROLE_THEME.unassigned;
  const active = isActiveStatus(statusLabel);
  const spriteSrc = active ? "/sprites/pixel-cat-working.svg" : "/sprites/pixel-cat-idle.svg";

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => setReducedMotion(mediaQuery.matches);

    syncPreference();
    mediaQuery.addEventListener?.("change", syncPreference);

    return () => {
      mediaQuery.removeEventListener?.("change", syncPreference);
    };
  }, []);

  const shouldAnimate = process.env.NODE_ENV !== "test" && !reducedMotion;

  return (
    <div className={clsx("flex items-center gap-3", className)}>
      <div
        className={clsx(
          "flex h-[74px] w-[74px] items-center justify-center overflow-hidden rounded-[1.25rem] border-4 shadow-[6px_6px_0_0_rgba(15,23,42,0.08)]",
          theme.frame
        )}
        aria-hidden="true"
      >
        <div
          className={clsx(
            "pixel-sprite pixel-cat-sprite",
            shouldAnimate ? (active ? "pixel-cat-working" : "pixel-cat-idle") : null
          )}
          style={{ backgroundImage: `url(${spriteSrc})` }}
        />
      </div>

      <div className="space-y-1">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-500">{theme.chip}</p>
        <p className={clsx("text-xs font-semibold tracking-[0.08em]", theme.accent)}>{theme.label}</p>
      </div>
    </div>
  );
}
