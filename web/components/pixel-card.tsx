import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PixelCardProps {
  title: string;
  eyebrow?: string;
  className?: string;
  children: ReactNode;
}

export function PixelCard({ title, eyebrow, className, children }: PixelCardProps) {
  // 所有工作台面板都共用同一組像素邊框與標題結構，方便整體視覺一致。
  return (
    <section className={cn("pixel-panel rounded-none p-4 md:p-5", className)}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          {eyebrow ? (
            <p className="mb-2 text-[10px] uppercase tracking-[0.28em] text-slate-500">{eyebrow}</p>
          ) : null}
          <h2 className="pixel-title text-lg leading-7 font-black tracking-[0.08em] text-ink">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}
