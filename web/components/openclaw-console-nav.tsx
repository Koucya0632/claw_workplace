"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/openclaw", label: "總覽" },
  { href: "/openclaw/instances", label: "實例" },
  { href: "/openclaw/agents", label: "Agents" },
  { href: "/openclaw/workflow", label: "Workflow" },
  { href: "/openclaw/devices", label: "Devices" },
  { href: "/openclaw/config", label: "Config" },
  { href: "/openclaw/logs", label: "Logs" },
  { href: "/openclaw/actions", label: "Actions" }
];

export function OpenClawConsoleNav() {
  // OpenClaw 管理頁很多，子導覽統一抽出來比較不會每頁各自飄掉。
  const pathname = usePathname();

  return (
    <div className="flex flex-wrap gap-2">
      {NAV_ITEMS.map((item) => {
        const active = item.href === "/openclaw" ? pathname === item.href : pathname.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "pixel-button px-3 py-2 text-xs font-black tracking-[0.08em]",
              active ? "bg-ink text-sand" : "bg-white text-ink"
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
