import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useMemo } from "react";
import { PriceHistoryRead } from "@/lib/api";

const periods = ["1W", "1M", "3M", "6M", "1Y"] as const;

const daysByPeriod: Record<string, number> = {
  "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365,
};

const STORE_CHART_COLORS: Record<string, string> = {
  "notino":         "hsl(187, 94%, 43%)",
  "notino.lv":      "hsl(187, 94%, 43%)",
  "douglas latvia": "hsl(217, 91%, 60%)",
  "douglas.lv":     "hsl(217, 91%, 60%)",
  "makeup.lv":      "hsl(330, 81%, 60%)",
  "makeup":         "hsl(330, 81%, 60%)",
  "1a.lv":          "hsl(25, 95%, 53%)",
  "220.lv":         "hsl(43, 96%, 56%)",
};

function storeChartColor(name: string): string {
  return STORE_CHART_COLORS[name.toLowerCase()] ?? "hsl(263, 70%, 58%)";
}

interface ChartPoint {
  date: string;
  fullDate: string;
  price: number;
}

function buildChartData(history: PriceHistoryRead[], days: number): ChartPoint[] {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  return history
    .filter(h => new Date(h.parsed_at) >= cutoff)
    .sort((a, b) => new Date(a.parsed_at).getTime() - new Date(b.parsed_at).getTime())
    .map(h => {
      const d = new Date(h.parsed_at);
      return {
        date: d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
        fullDate: d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }),
        price: +Number(h.price).toFixed(2),
      };
    });
}

function CustomTooltip({ active, payload, storeName }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-modal border border-primary/30 bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] shadow-card px-4 py-3 min-w-[180px] animate-tooltip-fade">
      <p className="text-[13px] font-semibold text-foreground mb-2">{item.payload.fullDate}</p>
      <div className="flex items-center justify-between gap-4 py-0.5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: item.color }} />
          <span className="text-[12px] text-muted-foreground">{storeName}</span>
        </div>
        <span className="text-[13px] font-semibold text-foreground price-display">
          {item.value.toFixed(2)} €
        </span>
      </div>
    </div>
  );
}

interface Props {
  period: string;
  onPeriodChange: (p: string) => void;
  history: PriceHistoryRead[];
  storeName: string;
}

export default function PriceChart({ period, onPeriodChange, history, storeName }: Props) {
  const color = storeChartColor(storeName);
  const data = useMemo(
    () => buildChartData(history, daysByPeriod[period] ?? 30),
    [history, period]
  );
  const tickInterval = data.length <= 14 ? 1 : Math.floor(data.length / 7);

  return (
    <div className="flex-1 flex flex-col min-w-0 p-6 gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold font-display text-foreground">Price History</h2>
        <div className="flex gap-1">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => onPeriodChange(p)}
              className={`px-3 py-1.5 rounded-full text-[12px] font-semibold transition-colors ${
                period === p
                  ? "bg-primary text-primary-foreground"
                  : "bg-surface-2 text-muted-foreground hover:text-foreground"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-[340px]">
        {data.length === 0 ? (
          <div className="h-full flex items-center justify-center text-muted-foreground text-[13px]">
            No price history for this period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradient-main" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(0 0% 100% / 0.05)"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                tickLine={false}
                axisLine={false}
                interval={tickInterval}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v} €`}
                width={60}
                domain={["auto", "auto"]}
              />
              <Tooltip
                content={<CustomTooltip storeName={storeName} />}
                cursor={{ stroke: color, strokeDasharray: "4 4", strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke={color}
                strokeWidth={2.5}
                fill="url(#gradient-main)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: color, fill: "hsl(240, 33%, 5%)" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-[12px]">
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
          <span className="text-muted-foreground">{storeName}</span>
        </div>
      </div>
    </div>
  );
}
