import { useEffect, useState } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { RefreshCw } from "lucide-react";
import { api, MoversDistributionBin } from "@/lib/api";

interface Props {
  window: "24h" | "7d" | "30d";
}

const SUCCESS = "hsl(142, 70%, 45%)";
const DESTRUCTIVE = "hsl(0, 70%, 55%)";
const NEUTRAL = "hsl(220, 12%, 35%)";

function tone(lower: number, upper: number) {
  if (upper <= 0) return SUCCESS; // drop bin
  if (lower >= 0) return DESTRUCTIVE; // rise bin
  return NEUTRAL; // straddles zero (shouldn't happen with our edges)
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-background shadow-card px-3 py-2 min-w-[140px]">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1">{label}</p>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11px] text-muted-foreground">Products</span>
        <span className="font-mono tabular-nums font-semibold text-[12.5px] text-foreground">
          {payload[0].value}
        </span>
      </div>
    </div>
  );
}

export default function MoversHistogram({ window }: Props) {
  const [bins, setBins] = useState<MoversDistributionBin[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getMoversDistribution(window, 5, 30)
      .then((d) => {
        if (!cancelled) setBins(d);
      })
      .catch(() => {
        if (!cancelled) setBins([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  const total = bins.reduce((s, b) => s + b.count, 0);
  const drops = bins.filter((b) => b.upper <= 0).reduce((s, b) => s + b.count, 0);
  const rises = bins.filter((b) => b.lower >= 0).reduce((s, b) => s + b.count, 0);

  return (
    <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Distribution · {window}
        </span>
        <div className="flex items-center gap-3 font-mono text-[10px] tabular-nums">
          <span className="text-[hsl(var(--success))]">↓ {drops}</span>
          <span className="text-muted-foreground/60">·</span>
          <span className="text-destructive">↑ {rises}</span>
          <span className="text-muted-foreground/60">·</span>
          <span className="text-muted-foreground">{total} total</span>
        </div>
      </div>

      <div className="h-[180px] px-1 pt-2">
        {loading ? (
          <div className="h-full flex items-center justify-center gap-2">
            <RefreshCw className="animate-spin text-muted-foreground" size={14} />
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              Loading
            </span>
          </div>
        ) : bins.length === 0 || total === 0 ? (
          <div className="h-full flex items-center justify-center">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              No movements in this window
            </span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bins} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 9, fill: "hsl(220, 12%, 55%)", fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                interval={0}
                angle={-35}
                textAnchor="end"
                height={50}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(220, 12%, 55%)", fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                width={32}
                allowDecimals={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(0 0% 100% / 0.04)" }} />
              <ReferenceLine x="0..+5%" stroke="hsl(220, 12%, 35%)" strokeDasharray="2 3" />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {bins.map((b, i) => (
                  <Cell key={i} fill={tone(b.lower, b.upper)} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
