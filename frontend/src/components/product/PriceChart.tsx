import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useMemo } from "react";
import { PriceHistoryRead } from "@/lib/api";

const periods = ["1W", "1M", "3M", "6M", "1Y"] as const;

const daysByPeriod: Record<string, number> = {
  "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365,
};

// Per-store line colors. Keys are canonical lowercase domains (matching
// PriceHistoryRead.store_name format coming from backend).
const STORE_COLORS: Record<string, string> = {
  "douglas.lv": "#3CB6B0", // teal
  "notino.lv":  "#3B82F6", // blue
  "220.lv":     "#F59E0B", // amber
  "makeup.lv":  "#EC4899", // pink
  "1a.lv":      "#8B5CF6", // violet
};
const FALLBACK_COLOR = "#94A3B8";

function colorFor(store: string): string {
  return STORE_COLORS[store.toLowerCase()] ?? FALLBACK_COLOR;
}

function storeLabel(store: string): string {
  // Pretty display label — match what's shown in catalog/feed
  const map: Record<string, string> = {
    "douglas.lv": "Douglas",
    "notino.lv": "Notino",
    "220.lv": "220.lv",
    "makeup.lv": "Makeup",
    "1a.lv": "1a.lv",
  };
  return map[store.toLowerCase()] ?? store;
}

/** Single point — has a `date` (display) and a numeric column per store. */
interface ChartPoint {
  date: string;
  fullDate: string;
  ts: number;          // unix ms for sorting
  [storeKey: string]: number | string; // e.g. "douglas.lv": 65.25
}

function buildMultiStoreData(
  history: PriceHistoryRead[],
  days: number,
): { rows: ChartPoint[]; stores: string[] } {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);

  const filtered = history.filter(h => new Date(h.parsed_at) >= cutoff);

  // Discover unique stores present in this window
  const stores = Array.from(new Set(filtered.map(h => (h.store_name ?? "").toLowerCase()).filter(Boolean)));

  // Map each timestamp to a row; multiple stores at the same ts merge into one row
  const byTs = new Map<number, ChartPoint>();
  for (const h of filtered) {
    const d = new Date(h.parsed_at);
    const ts = d.getTime();
    let row = byTs.get(ts);
    if (!row) {
      row = {
        date: d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
        fullDate: d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }),
        ts,
      };
      byTs.set(ts, row);
    }
    const store = (h.store_name ?? "").toLowerCase();
    if (store) {
      row[store] = +Number(h.price).toFixed(2);
    }
  }

  const rows = Array.from(byTs.values()).sort((a, b) => a.ts - b.ts);
  return { rows, stores };
}

interface TooltipPayload {
  color: string;
  dataKey: string;
  value: number;
  payload: ChartPoint;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null;
  const fullDate = payload[0]?.payload.fullDate;
  return (
    <div className="rounded-md border border-border bg-background shadow-card px-3 py-2 min-w-[200px]">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-1.5">
        {fullDate}
      </p>
      <div className="flex flex-col gap-1">
        {payload
          .filter((p) => p.value != null)
          .map((p) => (
            <div key={p.dataKey} className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: p.color }} />
                <span className="text-[12px] text-muted-foreground">{storeLabel(p.dataKey)}</span>
              </div>
              <span className="font-mono tabular-nums font-semibold text-[13px] text-foreground">
                {p.value.toFixed(2)} €
              </span>
            </div>
          ))}
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
  const { rows, stores } = useMemo(
    () => buildMultiStoreData(history, daysByPeriod[period] ?? 30),
    [history, period]
  );
  const tickInterval = rows.length <= 14 ? 1 : Math.floor(rows.length / 7);

  // Aggregate min/max across ALL stores in the window — for footer stats
  const allPrices: number[] = [];
  for (const row of rows) {
    for (const s of stores) {
      const v = row[s];
      if (typeof v === "number") allPrices.push(v);
    }
  }

  // For the period delta we use the first and last point of the PRIMARY (current
  // product's) store if it has data; otherwise fall back to the first available.
  const primaryStore = storeName.toLowerCase();
  const primaryRows = rows.filter((r) => typeof r[primaryStore] === "number");
  const fallbackStore = stores[0] ?? primaryStore;
  const lineRows = primaryRows.length ? primaryRows : rows.filter((r) => typeof r[fallbackStore] === "number");
  const lineStore = primaryRows.length ? primaryStore : fallbackStore;
  const earliest = lineRows.length ? (lineRows[0][lineStore] as number) : 0;
  const latest = lineRows.length ? (lineRows[lineRows.length - 1][lineStore] as number) : 0;
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
          <div className="flex items-baseline gap-3 flex-wrap">
            <h2 className="font-['Inter'] font-semibold text-foreground text-[18px] tracking-[-0.01em]">
              {stores.length > 1 ? `${stores.length} stores` : storeName}
            </h2>
            {lineRows.length > 1 && (
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
        {rows.length === 0 ? (
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
            <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
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
                content={<CustomTooltip />}
                cursor={{ stroke: FALLBACK_COLOR, strokeDasharray: "3 3", strokeWidth: 1 }}
              />
              {stores.length > 1 && (
                <Legend
                  wrapperStyle={{ fontSize: 11, fontFamily: "var(--font-mono, monospace)" }}
                  formatter={(value) => storeLabel(String(value))}
                  iconType="circle"
                />
              )}
              {stores.map((s) => {
                // Count actual data points for this store. If only 1 point, force
                // a visible dot — `dot={false}` would render nothing (Recharts
                // doesn't connect a single point into anything). Multi-point series
                // look cleaner without per-point dots.
                const points = rows.filter((r) => typeof r[s] === "number").length;
                return (
                  <Line
                    key={s}
                    type="monotone"
                    dataKey={s}
                    name={s}
                    stroke={colorFor(s)}
                    strokeWidth={2}
                    dot={points <= 1 ? { r: 4, strokeWidth: 2, stroke: colorFor(s), fill: "hsl(220, 30%, 8%)" } : false}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: colorFor(s), fill: "hsl(220, 30%, 8%)" }}
                    connectNulls
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Footer meta */}
      {rows.length > 0 && (
        <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-border">
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            {rows.length} data points · {stores.length} {stores.length === 1 ? "store" : "stores"}
          </span>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="font-mono text-muted-foreground">
              Low <span className="tabular-nums text-foreground">
                {allPrices.length ? Math.min(...allPrices).toFixed(2) : "—"} €
              </span>
            </span>
            <span className="font-mono text-muted-foreground">
              High <span className="tabular-nums text-foreground">
                {allPrices.length ? Math.max(...allPrices).toFixed(2) : "—"} €
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
