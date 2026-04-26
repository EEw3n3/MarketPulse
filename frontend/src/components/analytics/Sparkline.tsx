import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

interface Props {
  data: { avg_price: number }[];
  tone?: "primary" | "success" | "destructive" | "neutral";
  height?: number;
  width?: number | string;
}

const TONES: Record<NonNullable<Props["tone"]>, string> = {
  primary: "hsl(180, 70%, 45%)",
  success: "hsl(142, 70%, 45%)",
  destructive: "hsl(0, 70%, 55%)",
  neutral: "hsl(220, 12%, 55%)",
};

/**
 * Tiny inline area chart. No axes, no tooltip — purely shape-of-trend.
 * For per-row visualization (retailer profile rows, etc.).
 */
export default function Sparkline({ data, tone = "primary", height = 28, width = "100%" }: Props) {
  if (!data || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center font-mono text-[9px] text-muted-foreground/40"
        style={{ height, width }}
      >
        no data
      </div>
    );
  }

  const color = TONES[tone];
  const id = `spark-${tone}-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <div style={{ height, width }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={["auto", "auto"]} />
          <Area
            type="monotone"
            dataKey="avg_price"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${id})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
