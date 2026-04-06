import { PixelCard } from "@/components/pixel-card";
import type { SourceMetricsResponse } from "@/lib/types";

export function SourceMetricsGrid({ metrics }: { metrics: SourceMetricsResponse }) {
  const metricCards = [
    { label: "資料源總數", value: metrics.total_sources, tone: "bg-white" },
    { label: "正常來源", value: metrics.healthy_sources, tone: "bg-mint/70" },
    { label: "異常來源", value: metrics.warning_sources + metrics.failed_sources, tone: "bg-coral/15" },
    { label: "同步中", value: metrics.syncing_sources, tone: "bg-gold/40" },
    { label: "停用中", value: metrics.disabled_sources, tone: "bg-slate-100" },
    { label: "近 7 天更新", value: metrics.recently_updated_sources, tone: "bg-sky-100/70" },
    { label: "近期同步失敗", value: metrics.recent_sync_failures, tone: "bg-amber-100/80" }
  ];

  return (
    <PixelCard title="資料源總覽" eyebrow="Dashboard">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((metric) => (
          <article key={metric.label} className={`border-4 border-ink p-4 ${metric.tone}`}>
            <p className="text-[10px] uppercase tracking-[0.24em] text-slate-500">{metric.label}</p>
            <p className="mt-3 text-3xl font-black text-ink">{metric.value}</p>
          </article>
        ))}
      </div>
    </PixelCard>
  );
}
