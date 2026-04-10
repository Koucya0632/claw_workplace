"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/search", label: "搜索" },
  { href: "/settings/sources", label: "資料源" },
  { href: "/openclaw", label: "OpenClaw Control Center" }
];

export function Navigation() {
  // 目前頁面會以反白方式標示，讓工作台切換更直覺。
  const pathname = usePathname();

  return (
    <nav className="page-intro pixel-grid bg-grid-fade rounded-[1.75rem] px-4 py-4 md:px-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-[0.32em] text-slate-500">OpenClaw Phase 1</p>
          <div className="flex flex-col gap-1 lg:flex-row lg:items-baseline lg:gap-4">
            <h1 className="pixel-title text-xl leading-8 font-black tracking-[0.06em] text-ink md:text-2xl">
              智能辦公室工作台
            </h1>
            <p className="text-sm text-slate-600">Search、Sources 與 OpenClaw 統一在同一個板塊骨架中切換。</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "site-nav-link rounded-full px-4 py-2 text-sm font-black tracking-[0.05em]",
                  active ? "site-nav-link-active" : ""
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
