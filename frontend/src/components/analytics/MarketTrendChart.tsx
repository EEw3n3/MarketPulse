import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { api, MarketTrendPoint } from "@/lib/api";
import { cn } from "@/lib/utils";

const TEAL = "hsl(180, 70%, 45%)";
type Window = "7d" | "30d" | "90d";
const WINDOWS: Window[] = ["7d", "30d", "90d"];

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  const obs = item.payload.observation_count;
  return (
    <div className="rounded-md border border-border bg-background shadow-card px-3 py-2 min-w-[160px]">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1.5">
        {item.payload.date}
      </p>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[12px] text-muted-foreground">Avg price</span>
        <span className="font-mono tabular-nums font-semibold text-[13px] text-foreground">
          {item.value.toFixed(2)} €
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-3 mt-0.5">
        <span className="text-[11px] text-muted-foreground">Observations</span>
        <span className="font-mono tabular-nums text-[11px] text-muted-foreground">{obs}</span>
      </div>
    </div>
  );
}

export default function MarketTrendChart() {
  const [window, setWindow] = useState<Window>("30d");
  const [data, setData] = useState<MarketTrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getMarketTrend(window)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setData([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  const first = data[0]?.avg_price;
  const last = data[data.length - 1]?.avg_price;
  const deltaPct = first && first > 0 ? ((last - first) / first) * 100 : 0;
  const deltaDown = deltaPct < -0.05;
  const deltaUp = deltaPct > 0.05;

  return (
    <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center justify-between flex-wrap gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Market average · {window}
          </span>
          <div className="flex items-baseline gap-2">
            <span className="font-mono font-semibold tabular-nums text-foreground text-[16px]">
              {last ? `${last.toFixed(2)} €` : "—"}
            </span>
            {data.length > 1 && (
              <span
                className={cn(
                  "font-mono tabular-nums text-[11px] font-semibold",
                  deltaDown
                    ? "text-[hsl(var(--success))]"
                    : deltaUp
                    ? "text-destructive"
                    : "text-muted-foreground"
                )}
              >
                {deltaDown ? "−" : deltaUp ? "+" : ""}
                {Math.abs(deltaPct).toFixed(2)}%
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1 p-0.5 rounded-md border border-border bg-surface">
          {WINDOWS.map((w) => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={cn(
                "px-2.5 py-1 rounded font-mono text-[11px] font-medium tracking-wider transition-colors",
                window === w ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {w.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="h-[220px] px-2 pt-3">
        {loading ? (
          <div className="h-full flex items-center justify-center gap-2">
            <RefreshCw className="animate-spin text-muted-foreground" size={14} />
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              Loading
            </span>
          </div>
        ) : data.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              No data in this window
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 6, right: 12, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="market-trend-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={TEAL} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={TEAL} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="2 4" stroke="hsl(0 0% 100% / 0.04)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(d: string) => d.slice(5)}
                interval="preserveStartEnd"
                minTickGap={32}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v.toFixed(0)}€`}
                width={48}
                domain={["auto", "auto"]}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: TEAL, strokeDasharray: "3 3", strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="avg_price"
                stroke={TEAL}
                strokeWidth={1.75}
                fill="url(#market-trend-grad)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: TEAL, fill: "hsl(220, 30%, 8%)" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
