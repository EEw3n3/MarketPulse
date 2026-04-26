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

const TEAL = "hsl(180, 70%, 45%)";

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
    <div className="rounded-md border border-border bg-background shadow-card px-3 py-2 min-w-[180px]">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1.5">
        {item.payload.fullDate}
      </p>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: item.color }} />
          <span className="text-[12px] text-muted-foreground">{storeName}</span>
        </div>
        <span className="font-mono tabular-nums font-semibold text-[13px] text-foreground">
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
  const data = useMemo(
    () => buildChartData(history, daysByPeriod[period] ?? 30),
    [history, period]
  );
  const tickInterval = data.length <= 14 ? 1 : Math.floor(data.length / 7);

  const latest = data.length ? data[data.length - 1].price : 0;
  const earliest = data.length ? data[0].price : 0;
  const delta = latest - earliest;
  const deltaPct = earliest > 0 ? (delta / earliest) * 100 : 0;
  const deltaDown = delta < -0.01;
  const deltaUp = delta > 0.01;

  return (
    <div className="flex-1 flex flex-col min-w-0 p-6 lg:p-7 gap-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            02 · Price history
          </span>
          <div className="flex items-baseline gap-3">
            <h2 className="font-['Inter'] font-semibold text-foreground text-[18px] tracking-[-0.01em]">
              {storeName}
            </h2>
            {data.length > 1 && (
              <span
                className={`font-mono tabular-nums text-[12px] ${
                  deltaDown
                    ? "text-[hsl(var(--success))]"
                    : deltaUp
                    ? "text-destructive"
                    : "text-muted-foreground"
                }`}
              >
                {deltaDown ? "−" : deltaUp ? "+" : ""}
                {Math.abs(deltaPct).toFixed(1)}% · {period}
              </span>
            )}
          </div>
        </div>

        {/* Period pills */}
        <div className="flex items-center gap-1 p-0.5 rounded-md border border-border bg-surface">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => onPeriodChange(p)}
              className={`px-2.5 py-1 rounded font-mono text-[11px] font-medium tracking-wider transition-colors ${
                period === p
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground"
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
          <div className="h-full flex flex-col items-center justify-center gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              No data
            </span>
            <p className="text-[12.5px] text-muted-foreground">
              No price history recorded for this period.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradient-main" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={TEAL} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={TEAL} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="2 4"
                stroke="hsl(0 0% 100% / 0.04)"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "var(--font-mono, monospace)" }}
                tickLine={false}
                axisLine={false}
                interval={tickInterval}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "var(--font-mono, monospace)" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v} €`}
                width={56}
                domain={["auto", "auto"]}
              />
              <Tooltip
                content={<CustomTooltip storeName={storeName} />}
                cursor={{ stroke: TEAL, strokeDasharray: "3 3", strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke={TEAL}
                strokeWidth={1.75}
                fill="url(#gradient-main)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: TEAL, fill: "hsl(220, 30%, 8%)" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Footer meta */}
      {data.length > 0 && (
        <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-border">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            {data.length} data points
          </span>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="font-mono text-muted-foreground">
              Low <span className="tabular-nums text-foreground">{Math.min(...data.map(d => d.price)).toFixed(2)} €</span>
            </span>
            <span className="font-mono text-muted-foreground">
              High <span className="tabular-nums text-foreground">{Math.max(...data.map(d => d.price)).toFixed(2)} €</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
