import { useEffect, useState } from "react";
import { api, DashboardStats } from "@/lib/api";
import { Package, Store, DollarSign, BarChart3, TrendingDown } from "lucide-react";
import AnalyticsToc from "./AnalyticsToc";
import Reveal from "./Reveal";
import MarketTrendChart from "./MarketTrendChart";
import MoversSection from "./MoversSection";
import SpreadsSection from "./SpreadsSection";
import RetailersSection from "./RetailersSection";
import HeatmapSection from "./HeatmapSection";
import VolatilitySection from "./VolatilitySection";
import { useScrollSpy } from "@/hooks/use-scroll-spy";

const TOC = [
  { id: "overview", index: "00", label: "Overview" },
  { id: "movers", index: "01", label: "Movers" },
  { id: "spreads", index: "02", label: "Spreads" },
  { id: "retailers", index: "03", label: "Retailers" },
  { id: "heatmap", index: "04", label: "Heatmap" },
  { id: "volatility", index: "05", label: "Volatility" },
];

const KPI_DEFS = [
  { key: "total_products", label: "Products tracked", icon: Package },
  { key: "stores_monitored", label: "Stores monitored", icon: Store },
  { key: "avg_price_change", label: "Avg. price change · 30d", icon: TrendingDown },
  { key: "potential_savings", label: "Potential savings", icon: DollarSign },
  { key: "alerts_triggered", label: "Alerts (7d)", icon: BarChart3 },
] as const;

export default function AnalyticsContent() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(() => setStats(null));
  }, []);

  const active = useScrollSpy(
    TOC.map((t) => t.id),
    "[data-analytics-scroll]",
    140
  );

  return (
    <div className="flex-1 flex min-h-0 overflow-hidden">
      <AnalyticsToc sections={TOC} active={active} />

      <main
        data-analytics-scroll
        className="flex-1 overflow-y-auto pb-24"
      >
        {/* Page header */}
        <div className="border-b border-border px-7 pt-7 pb-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
            · B2B insights
          </p>
          <h1 className="font-['Inter'] font-semibold text-foreground text-[28px] tracking-[-0.015em]">
            Analytics
          </h1>
          <p className="text-[13px] text-muted-foreground mt-1.5 max-w-2xl">
            Aggregate views computed live from the catalog. Movements, arbitrage opportunities,
            retailer profiles, and volatility — all clickable through to product detail.
          </p>
        </div>

        {/* Section 00 — Overview */}
        <Reveal as="section" id="overview" className="px-7 pt-10 pb-12 border-b border-border">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
            00 · Overview
          </p>
          <h2 className="font-['Inter'] font-semibold text-foreground text-[22px] tracking-[-0.01em] mb-6">
            Portfolio at a glance
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-px bg-border rounded-md overflow-hidden border border-border mb-6">
            {KPI_DEFS.map(({ key, label, icon: Icon }) => {
              const value = stats ? (stats as Record<string, string | number>)[key] : "—";
              return (
                <div
                  key={key}
                  className="bg-surface/40 px-5 py-5 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
                      {label}
                    </span>
                    <Icon size={13} strokeWidth={1.5} className="text-muted-foreground" />
                  </div>
                  <span className="font-mono font-semibold tabular-nums tracking-tight text-foreground text-[24px]">
                    {value ?? "—"}
                  </span>
                </div>
              );
            })}
          </div>

          <MarketTrendChart />
        </Reveal>

        {/* Section 01 — Movers */}
        <Reveal as="section" id="movers" className="px-7 pt-12 pb-14 border-b border-border">
          <MoversSection />
        </Reveal>

        {/* Section 02 — Spreads */}
        <Reveal as="section" id="spreads" className="px-7 pt-12 pb-14 border-b border-border">
          <SpreadsSection />
        </Reveal>

        {/* Section 03 — Retailers */}
        <Reveal as="section" id="retailers" className="px-7 pt-12 pb-14 border-b border-border">
          <RetailersSection />
        </Reveal>

        {/* Section 04 — Heatmap */}
        <Reveal as="section" id="heatmap" className="px-7 pt-12 pb-14 border-b border-border">
          <HeatmapSection />
        </Reveal>

        {/* Section 05 — Volatility */}
        <Reveal as="section" id="volatility" className="px-7 pt-12 pb-20">
          <VolatilitySection />
        </Reveal>
      </main>
    </div>
  );
}
