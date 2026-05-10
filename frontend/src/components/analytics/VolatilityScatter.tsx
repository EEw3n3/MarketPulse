import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { api, VolatilityItem } from "@/lib/api";

const TEAL = "hsl(180, 70%, 45%)";

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as VolatilityItem;
  return (
    <div className="rounded-md border border-border bg-background shadow-card px-3 py-2 min-w-[200px]">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1 truncate">
        {p.brand ?? "—"} · {p.store_name}
      </p>
      <p className="text-[12px] text-foreground mb-1.5 truncate">{p.title}</p>
      <div className="flex items-baseline justify-between gap-3 font-mono text-[11px] tabular-nums">
        <span className="text-muted-foreground">Price</span>
        <span className="text-foreground font-semibold">{p.current_price.toFixed(2)} €</span>
      </div>
      <div className="flex items-baseline justify-between gap-3 font-mono text-[11px] tabular-nums">
        <span className="text-muted-foreground">σ</span>
        <span className="text-primary font-semibold">{p.volatility_eur.toFixed(2)} €</span>
      </div>
    </div>
  );
}

interface Props {
  window: "24h" | "7d" | "30d";
}

export default function VolatilityScatter({ window }: Props) {
  const navigate = useNavigate();
  const [points, setPoints] = useState<VolatilityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getVolatility(window, 100)
      .then((d) => {
        // Log scale on X-axis requires current_price > 0
        if (!cancelled) setPoints(d.filter((p) => p.current_price > 0 && p.volatility_eur >= 0));
      })
      .catch(() => {
        if (!cancelled) setPoints([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  return (
    <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Price × Volatility · {window}
        </span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {points.length} products
        </span>
      </div>

      <div className="h-[260px] px-1 pt-2 pr-3">
        {loading ? (
          <div className="h-full flex items-center justify-center gap-2">
            <RefreshCw className="animate-spin text-muted-foreground" size={14} />
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              Loading
            </span>
          </div>
        ) : points.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              No volatility data in this window
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 12, left: 4, bottom: 28 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="hsl(0 0% 100% / 0.04)" />
              <XAxis
                dataKey="current_price"
                type="number"
                scale="log"
                domain={[1, "dataMax"]}
                allowDataOverflow={false}
                ticks={[3, 10, 30, 100, 300, 1000]}
                name="Price"
                unit=" €"
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v.toFixed(0)}€`}
                label={{
                  value: "Current price (log)",
                  position: "insideBottom",
                  offset: -16,
                  style: { fill: "hsl(220, 12%, 55%)", fontSize: 10, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.14em" },
                }}
              />
              <YAxis
                dataKey="volatility_eur"
                type="number"
                name="Volatility"
                unit=" €"
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v.toFixed(0)}€`}
                width={42}
                label={{
                  value: "σ",
                  position: "insideTopLeft",
                  offset: 8,
                  style: { fill: "hsl(220, 12%, 55%)", fontSize: 11, fontFamily: "monospace" },
                }}
              />
              <ZAxis dataKey="observation_count" range={[40, 160]} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: TEAL, strokeDasharray: "3 3" }} />
              <Scatter
                data={points}
                fill={TEAL}
                fillOpacity={0.55}
                stroke={TEAL}
                strokeOpacity={0.9}
                onClick={(p: any) => p?.product_id && navigate(`/product/${p.product_id}`)}
                cursor="pointer"
              />
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="px-4 py-2 border-t border-border flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        <span>Bubble size = # observations</span>
        <span className="text-muted-foreground/50">·</span>
        <span>Top-right quadrant = best alert candidates</span>
      </div>
    </div>
  );
}
