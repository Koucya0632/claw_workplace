"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "主控台" },
  { href: "/search", label: "搜索" },
  { href: "/analysis", label: "分析" },
  { href: "/report", label: "報告" },
  { href: "/settings/sources", label: "資料源" }
];

export function Navigation() {
  // 目前頁面會以反白方式標示，讓工作台切換更直覺。
  const pathname = usePathname();

  return (
    <nav className="pixel-panel pixel-grid bg-grid-fade rounded-none p-3">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.35em] text-slate-500">OpenClaw Phase 1</p>
          <h1 className="pixel-title mt-2 text-xl leading-8 font-black uppercase tracking-[0.08em] text-ink">
            智能辦公室工作台
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "pixel-button px-3 py-2 text-sm font-black tracking-[0.08em]",
                  active ? "bg-ink text-sand" : "bg-sand text-ink"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
