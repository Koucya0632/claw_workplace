import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PixelCardProps {
  title: string;
  eyebrow?: string;
  variant?: "panel" | "inset" | "muted";
  density?: "comfortable" | "compact";
  headerActions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

const VARIANT_CLASS_MAP = {
  panel: "card-panel",
  inset: "card-inset",
  muted: "card-muted",
} as const;

const DENSITY_CLASS_MAP = {
  comfortable: "p-5 md:p-6",
  compact: "p-4 md:p-5",
} as const;

export function PixelCard({
  title,
  eyebrow,
  variant = "panel",
  density = "comfortable",
  headerActions,
  className,
  bodyClassName,
  children
}: PixelCardProps) {
  // 所有工作台面板都共用同一組像素邊框與標題結構，方便整體視覺一致。
  return (
    <section
      className={cn(
        "rounded-[1.5rem]",
        VARIANT_CLASS_MAP[variant],
        DENSITY_CLASS_MAP[density],
        className
      )}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          {eyebrow ? (
            <p className="mb-2 text-[10px] uppercase tracking-[0.24em] text-slate-500">{eyebrow}</p>
          ) : null}
          <h2 className="pixel-title text-lg leading-7 font-black tracking-[0.05em] text-ink">{title}</h2>
        </div>
        {headerActions ? <div className="shrink-0">{headerActions}</div> : null}
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
