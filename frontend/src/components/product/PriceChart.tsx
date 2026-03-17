import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useState, useMemo } from "react";

const periods = ["1W", "1M", "3M", "6M", "1Y"] as const;

// Generate mock data
function generateData(days: number) {
  const data: Record<string, any>[] = [];
  const now = new Date(2026, 2, 16);
  const baseD = 130, baseN = 135, base1 = 140;
  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    data.push({
      date: d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
      fullDate: d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }),
      douglas: +(baseD - Math.sin(i * 0.15) * 8 - i * 0.12).toFixed(2),
      notino: +(baseN - Math.cos(i * 0.12) * 6 - i * 0.1).toFixed(2),
      "1a": +(base1 - Math.sin(i * 0.1 + 1) * 5 - i * 0.08).toFixed(2),
    });
  }
  return data;
}

const daysByPeriod: Record<string, number> = {
  "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365,
};

const storeColors: Record<string, string> = {
  douglas: "hsl(263, 70%, 58%)",
  notino: "hsl(187, 94%, 43%)",
  "1a": "hsl(220, 9%, 46%)",
};

const storeLabels: Record<string, string> = {
  douglas: "Douglas.lv",
  notino: "Notino.lv",
  "1a": "1a.lv",
};

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-modal border border-primary/30 bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] shadow-card px-4 py-3 min-w-[180px] animate-tooltip-fade">
      <p className="text-[13px] font-semibold text-foreground mb-2">{item.payload.fullDate}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 py-0.5">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-[12px] text-muted-foreground">{storeLabels[p.dataKey]}</span>
          </div>
          <span className="text-[13px] font-semibold text-foreground price-display">{p.value.toFixed(2)} €</span>
        </div>
      ))}
    </div>
  );
}

interface Props {
  period: string;
  onPeriodChange: (p: string) => void;
}

export default function PriceChart({ period, onPeriodChange }: Props) {
  const [visibleStores, setVisibleStores] = useState<Set<string>>(
    new Set(["douglas", "notino", "1a"])
  );

  const data = useMemo(() => generateData(daysByPeriod[period] || 30), [period]);

  const toggleStore = (key: string) => {
    setVisibleStores((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Determine tick interval based on data length
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
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              {Object.entries(storeColors).map(([key, color]) => (
                <linearGradient key={key} id={`gradient-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              ))}
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
              content={<CustomTooltip />}
              cursor={{
                stroke: "hsl(263, 70%, 58%)",
                strokeDasharray: "4 4",
                strokeWidth: 1,
              }}
            />
            {Object.keys(storeColors).map((key) =>
              visibleStores.has(key) ? (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={storeColors[key]}
                  strokeWidth={2.5}
                  fill={`url(#gradient-${key})`}
                  dot={false}
                  activeDot={{
                    r: 5,
                    strokeWidth: 2,
                    stroke: storeColors[key],
                    fill: "hsl(240, 33%, 5%)",
                  }}
                />
              ) : null
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4">
        {Object.entries(storeLabels).map(([key, label]) => (
          <button
            key={key}
            onClick={() => toggleStore(key)}
            className={`flex items-center gap-2 text-[12px] transition-opacity ${
              visibleStores.has(key) ? "opacity-100" : "opacity-40"
            }`}
          >
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: storeColors[key] }}
            />
            <span className="text-muted-foreground">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
