import { useEffect, useState } from "react";
import { api, RetailerStats, RetailerTrendSeries } from "@/lib/api";
import SectionHeader from "./SectionHeader";
import Sparkline from "./Sparkline";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvija$/i, "").trim().slice(0, 2).toUpperCase();
}

function ProgressBar({ value, tone = "neutral" }: { value: number; tone?: "neutral" | "success" }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = tone === "success" ? "bg-[hsl(var(--success))]" : "bg-foreground";
  return (
    <div className="w-full h-1 bg-surface-2 rounded-full overflow-hidden">
      <div
        className={`h-full ${color} rounded-full transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function RetailersSection() {
  const [items, setItems] = useState<RetailerStats[]>([]);
  const [trends, setTrends] = useState<Record<string, RetailerTrendSeries["points"]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([api.getRetailers(), api.getRetailersTrend("30d")])
      .then(([profiles, series]) => {
        if (cancelled) return;
        setItems(profiles);
        const map: Record<string, RetailerTrendSeries["points"]> = {};
        for (const s of series) map[s.store] = s.points;
        setTrends(map);
      })
      .catch((err) => {
        console.error("Failed to load retailers:", err);
        if (!cancelled) setError("Could not load retailer profiles.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const maxProducts = Math.max(...items.map((r) => r.product_count), 1);

  return (
    <>
      <SectionHeader
        index="03"
        label="Retailers"
        title="Per-retailer profile"
        description="How each store ranks on coverage, average price, drop activity, and how often they win the cheapest-price slot."
      />

      {loading ? (
        <LoadingState label="Loading retailers" />
      ) : error ? (
        <ErrorState message={error} />
      ) : items.length === 0 ? (
        <EmptyState message="No retailers yet." />
      ) : (
        <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
          <div className="grid grid-cols-[160px_1fr_110px_140px_110px_140px] gap-4 px-5 py-3 border-b border-border bg-surface/60">
            {["Retailer", "Coverage", "Avg price", "Trend · 30d", "Drop rate", "Cheapest wins"].map((h) => (
              <span
                key={h}
                className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-medium"
              >
                {h}
              </span>
            ))}
          </div>

          <div className="divide-y divide-border">
            {items.map((r) => {
              const points = trends[r.store] ?? [];
              const first = points[0]?.avg_price;
              const last = points[points.length - 1]?.avg_price;
              const trendDir =
                first && first > 0
                  ? last < first - 0.05
                    ? "success"
                    : last > first + 0.05
                    ? "destructive"
                    : "neutral"
                  : "neutral";
              return (
                <div
                  key={r.store}
                  className="grid grid-cols-[160px_1fr_110px_140px_110px_140px] gap-4 px-5 py-4 items-center"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-7 h-5 rounded-sm bg-surface-2 border border-border font-mono text-[9px] font-medium text-muted-foreground flex items-center justify-center shrink-0">
                      {storeTag(r.store)}
                    </span>
                    <span className="text-[13px] text-foreground truncate">{r.store}</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <ProgressBar value={(r.product_count / maxProducts) * 100} />
                    </div>
                    <span className="font-mono tabular-nums text-[11.5px] text-foreground w-12 shrink-0 text-right">
                      {r.product_count}
                    </span>
                  </div>

                  <span className="font-mono tabular-nums text-[12.5px] font-semibold text-foreground">
                    {r.avg_price.toFixed(2)} €
                  </span>

                  <Sparkline data={points} tone={trendDir as any} height={24} />

                  <div className="flex items-baseline gap-1.5">
                    <span className="font-mono tabular-nums text-[12.5px] font-semibold text-foreground">
                      {r.drop_rate.toFixed(1)}%
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      ({r.drop_count})
                    </span>
                  </div>

                  <div className="flex items-center gap-2.5">
                    <div className="flex-1">
                      <ProgressBar value={r.cheapest_win_rate} tone="success" />
                    </div>
                    <span className="font-mono tabular-nums text-[11.5px] text-foreground w-12 shrink-0 text-right">
                      {r.cheapest_win_rate.toFixed(0)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
