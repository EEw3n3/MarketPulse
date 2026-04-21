import { useState, useMemo, useEffect } from "react";
import { api, DashboardStats } from "@/lib/api";
import {
  TrendingDown,
  TrendingUp,
  BarChart3,
  DollarSign,
  Package,
  Store,
  ArrowUp,
  ArrowDown,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import PriceSpikeHeatmap from "./PriceSpikeHeatmap";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ───── Static KPI structure ─────
const kpiBase = [
  { label: "Products Tracked", icon: Package, direction: "up" },
  { label: "Avg. Price Change", icon: TrendingDown, direction: "down" },
  { label: "Stores Monitored", icon: Store, direction: "up" },
  { label: "Potential Savings", icon: DollarSign, direction: "up" },
  { label: "Price Alerts", icon: BarChart3, direction: "up" },
];

export default function AnalyticsContent() {
  const [period, setPeriod] = useState<string>("1Y");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getStats()
      .then(data => { if (!cancelled) setStats(data); })
      .catch(err => {
        console.error("Failed to load analytics stats:", err);
        if (!cancelled) setError(err?.message ?? "Could not load analytics.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const kpis = useMemo(() => {
    if (!stats) return [];
    return [
      { ...kpiBase[0], value: stats.total_products, change: "+12%" },
      { ...kpiBase[1], value: stats.avg_price_change, change: "last 30d" },
      { ...kpiBase[2], value: String(stats.stores_monitored), change: "active" },
      { ...kpiBase[3], value: stats.potential_savings, change: "available" },
      { ...kpiBase[4], value: String(stats.alerts_triggered), change: "new" },
    ];
  }, [stats]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-4">
        <RefreshCw className="animate-spin text-primary" size={32} />
        <p className="text-muted-foreground animate-pulse">Analyzing market data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-3 px-6 text-center">
        <AlertCircle className="text-destructive" size={28} />
        <p className="text-foreground font-medium">{error}</p>
        <p className="text-[13px] text-muted-foreground">Try refreshing the page.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-foreground">Analytics</h1>
            <p className="text-[13px] text-muted-foreground">Portfolio-level insights</p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {kpis.map((kpi) => (
            <Card key={kpi.label} className="bg-surface border-border transition-all">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] uppercase tracking-widest text-muted-foreground font-medium">{kpi.label}</span>
                  <kpi.icon size={14} className="text-muted-foreground" />
                </div>
                <p className="font-display text-2xl font-bold text-foreground tracking-tight">{kpi.value}</p>
                <p className={cn("text-[11px] mt-1 flex items-center gap-1", kpi.direction === "up" ? "text-[hsl(var(--success))]" : "text-destructive")}>
                  {kpi.change}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Placeholder for charts (will be connected in next phase) */}
        <Card className="bg-surface border-border p-8 text-center">
          <p className="text-muted-foreground">Detailed charts and Heatmap are ready for data binding.</p>
        </Card>
      </div>
    </div>
  );
}
