import { useState, useMemo } from "react";
import {
  TrendingDown,
  TrendingUp,
  BarChart3,
  DollarSign,
  Package,
  Store,
  ArrowUp,
  ArrowDown,
  Minus,
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
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
  PieChart,
  Pie,
} from "recharts";

// ───── KPI data ─────
const kpiCards = [
  {
    label: "Products Tracked",
    value: "2,847",
    change: "+124",
    changePercent: "+4.6%",
    direction: "up" as const,
    icon: Package,
  },
  {
    label: "Avg. Price Change",
    value: "-3.2%",
    change: "vs. -1.8% prev.",
    changePercent: "",
    direction: "down" as const,
    icon: TrendingDown,
  },
  {
    label: "Stores Monitored",
    value: "12",
    change: "+2 this month",
    changePercent: "",
    direction: "up" as const,
    icon: Store,
  },
  {
    label: "Potential Savings",
    value: "€14,320",
    change: "+€2,150",
    changePercent: "+17.6%",
    direction: "up" as const,
    icon: DollarSign,
  },
  {
    label: "Price Alerts Triggered",
    value: "342",
    change: "+56 this week",
    changePercent: "",
    direction: "up" as const,
    icon: BarChart3,
  },
];

// ───── Price trend data ─────
const trendData = [
  { date: "Jan", avgPrice: 82, minPrice: 54, maxPrice: 128 },
  { date: "Feb", avgPrice: 79, minPrice: 51, maxPrice: 125 },
  { date: "Mar", avgPrice: 84, minPrice: 56, maxPrice: 132 },
  { date: "Apr", avgPrice: 77, minPrice: 48, maxPrice: 119 },
  { date: "May", avgPrice: 73, minPrice: 45, maxPrice: 115 },
  { date: "Jun", avgPrice: 76, minPrice: 50, maxPrice: 122 },
  { date: "Jul", avgPrice: 71, minPrice: 43, maxPrice: 112 },
  { date: "Aug", avgPrice: 68, minPrice: 41, maxPrice: 108 },
  { date: "Sep", avgPrice: 72, minPrice: 46, maxPrice: 118 },
  { date: "Oct", avgPrice: 69, minPrice: 42, maxPrice: 110 },
  { date: "Nov", avgPrice: 74, minPrice: 49, maxPrice: 120 },
  { date: "Dec", avgPrice: 70, minPrice: 44, maxPrice: 114 },
];

// ───── Store comparison ─────
const storeComparison = [
  { store: "Notino", avgPrice: 67, products: 842, avgDiscount: 12.3, color: "hsl(263, 70%, 58%)" },
  { store: "Douglas", avgPrice: 78, products: 1204, avgDiscount: 8.1, color: "hsl(187, 94%, 43%)" },
  { store: "Sephora", avgPrice: 82, products: 956, avgDiscount: 6.7, color: "hsl(160, 84%, 39%)" },
  { store: "Parfumdreams", avgPrice: 71, products: 623, avgDiscount: 10.5, color: "hsl(45, 93%, 58%)" },
  { store: "Flaconi", avgPrice: 74, products: 518, avgDiscount: 9.8, color: "hsl(0, 84%, 60%)" },
];

// ───── Category breakdown ─────
const categoryData = [
  { name: "Eau de Parfum", value: 1240, fill: "hsl(263, 70%, 58%)" },
  { name: "Eau de Toilette", value: 860, fill: "hsl(187, 94%, 43%)" },
  { name: "Parfum", value: 420, fill: "hsl(160, 84%, 39%)" },
  { name: "Body Spray", value: 327, fill: "hsl(45, 93%, 58%)" },
];

// ───── Top movers ─────
const topMovers = [
  { brand: "Dior", name: "Sauvage EDP 100ml", change: -18.4, price: 72.50, previousPrice: 88.90, store: "Notino" },
  { brand: "Chanel", name: "Bleu de Chanel EDP 100ml", change: -14.2, price: 98.00, previousPrice: 114.20, store: "Douglas" },
  { brand: "YSL", name: "Y EDP 100ml", change: -12.8, price: 68.90, previousPrice: 79.00, store: "Notino" },
  { brand: "Tom Ford", name: "Ombré Leather 50ml", change: -11.5, price: 105.00, previousPrice: 118.60, store: "Sephora" },
  { brand: "Versace", name: "Eros EDT 100ml", change: -9.3, price: 52.40, previousPrice: 57.80, store: "Parfumdreams" },
  { brand: "Armani", name: "Acqua di Giò Profondo 75ml", change: +8.1, price: 84.30, previousPrice: 78.00, store: "Douglas" },
  { brand: "Prada", name: "Luna Rossa Carbon 100ml", change: +6.4, price: 76.90, previousPrice: 72.30, store: "Flaconi" },
  { brand: "Hermès", name: "Terre d'Hermès EDP 75ml", change: +5.2, price: 92.00, previousPrice: 87.50, store: "Sephora" },
];

// ───── Custom tooltip ─────
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-card border border-border bg-surface-2 px-3 py-2 text-xs shadow-card">
      <p className="mb-1 font-medium text-foreground">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} style={{ color: entry.color }} className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: entry.color }} />
          {entry.name}: €{entry.value}
        </p>
      ))}
    </div>
  );
}

// ───── Period selector ─────
const periods = ["1M", "3M", "6M", "1Y", "YTD"] as const;

export default function AnalyticsContent() {
  const [period, setPeriod] = useState<string>("1Y");

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-foreground">Analytics</h1>
            <p className="text-[13px] text-muted-foreground">
              Portfolio-level insights across all tracked products
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Select defaultValue="all">
              <SelectTrigger className="h-8 w-[140px] border-border bg-surface-2 text-xs">
                <SelectValue placeholder="All Brands" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Brands</SelectItem>
                <SelectItem value="dior">Dior</SelectItem>
                <SelectItem value="chanel">Chanel</SelectItem>
                <SelectItem value="ysl">YSL</SelectItem>
                <SelectItem value="tomford">Tom Ford</SelectItem>
              </SelectContent>
            </Select>
            <Select defaultValue="all-stores">
              <SelectTrigger className="h-8 w-[140px] border-border bg-surface-2 text-xs">
                <SelectValue placeholder="All Stores" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all-stores">All Stores</SelectItem>
                <SelectItem value="notino">Notino</SelectItem>
                <SelectItem value="douglas">Douglas</SelectItem>
                <SelectItem value="sephora">Sephora</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {kpiCards.map((kpi) => (
            <Card key={kpi.label} className="bg-surface border-border hover:-translate-y-1 hover:shadow-[0_12px_32px_rgba(0,0,0,0.4)] hover:border-primary/30 transition-all duration-300 group cursor-pointer">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] uppercase tracking-widest text-muted-foreground font-medium group-hover:text-foreground transition-colors">
                    {kpi.label}
                  </span>
                  <kpi.icon size={14} className="text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
                <p className="font-display text-2xl font-bold text-foreground tabular-nums tracking-tight">
                  {kpi.value}
                </p>
                <p className={cn(
                  "text-[11px] mt-1 flex items-center gap-1 font-display tabular-nums tracking-tight font-medium",
                  kpi.direction === "up" ? "text-[hsl(var(--success))]" : "text-destructive"
                )}>
                  {kpi.direction === "up" ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                  {kpi.change}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Price Trend Chart */}
          <Card className="lg:col-span-2 bg-surface border-border">
            <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
              <CardTitle className="text-sm font-medium text-foreground">
                Average Price Trend
              </CardTitle>
              <div className="flex items-center gap-1 rounded-lg bg-surface-2 p-0.5">
                {periods.map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-[11px] font-medium transition-all",
                      period === p
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="avgGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(263, 70%, 58%)" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="hsl(263, 70%, 58%)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="rangeGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(187, 94%, 43%)" stopOpacity={0.15} />
                        <stop offset="100%" stopColor="hsl(187, 94%, 43%)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 100% / 0.05)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v) => `€${v}`}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="maxPrice"
                      stroke="transparent"
                      fill="url(#rangeGradient)"
                      name="Max"
                    />
                    <Area
                      type="monotone"
                      dataKey="avgPrice"
                      stroke="hsl(263, 70%, 58%)"
                      strokeWidth={2}
                      fill="url(#avgGradient)"
                      name="Avg"
                    />
                    <Area
                      type="monotone"
                      dataKey="minPrice"
                      stroke="hsl(187, 94%, 43%)"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      fill="transparent"
                      name="Min"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Category Breakdown */}
          <Card className="bg-surface border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-foreground">
                Category Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categoryData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                      stroke="transparent"
                    >
                      {categoryData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload;
                        return (
                          <div className="rounded-card border border-border bg-surface-2 px-3 py-2 text-xs shadow-card">
                            <p className="font-medium text-foreground">{d.name}</p>
                            <p className="text-muted-foreground">{d.value.toLocaleString()} products</p>
                          </div>
                        );
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2 mt-2">
                {categoryData.map((c) => (
                  <div key={c.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.fill }} />
                      <span className="text-foreground">{c.name}</span>
                    </div>
                    <span className="text-muted-foreground tabular-nums">{c.value.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Store Comparison + Top Movers */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Store Comparison */}
          <Card className="bg-surface border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-foreground">
                Store Comparison
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={storeComparison} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(0 0% 100% / 0.05)" />
                    <XAxis
                      dataKey="store"
                      tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v) => `€${v}`}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="avgPrice" name="Avg Price" radius={[4, 4, 0, 0]}>
                      {storeComparison.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {/* Store metrics table */}
              <Table className="mt-3">
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-[11px] h-8">Store</TableHead>
                    <TableHead className="text-[11px] h-8 text-right">Products</TableHead>
                    <TableHead className="text-[11px] h-8 text-right">Avg. Discount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {storeComparison.map((s) => (
                    <TableRow key={s.store} className="border-border">
                      <TableCell className="py-2 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                          {s.store}
                        </div>
                      </TableCell>
                      <TableCell className="py-2 text-xs text-right tabular-nums">
                        {s.products.toLocaleString()}
                      </TableCell>
                      <TableCell className="py-2 text-xs text-right">
                        <Badge variant="outline" className="border-success/30 text-success text-[10px] px-1.5">
                          -{s.avgDiscount}%
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Top Movers */}
          <Card className="bg-surface border-border">
            <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
              <CardTitle className="text-sm font-medium text-foreground">
                Top Price Movers
              </CardTitle>
              <Tabs defaultValue="drops" className="w-auto">
                <TabsList className="h-7 p-0.5 bg-surface-2">
                  <TabsTrigger value="drops" className="text-[11px] h-6 px-2.5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                    Drops
                  </TabsTrigger>
                  <TabsTrigger value="increases" className="text-[11px] h-6 px-2.5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
                    Increases
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </CardHeader>
            <CardContent className="pt-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-[11px] h-8">Product</TableHead>
                    <TableHead className="text-[11px] h-8 text-right">Price</TableHead>
                    <TableHead className="text-[11px] h-8 text-right">Change</TableHead>
                    <TableHead className="text-[11px] h-8 text-right">Store</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {topMovers.map((item, i) => (
                    <TableRow key={i} className="border-border cursor-pointer hover:bg-surface-2/50">
                      <TableCell className="py-2">
                        <p className="text-xs font-medium text-foreground">{item.name}</p>
                        <p className="text-[10px] text-muted-foreground">{item.brand}</p>
                      </TableCell>
                      <TableCell className="py-2 text-xs text-right tabular-nums">
                        <span className="text-foreground">€{item.price.toFixed(2)}</span>
                        <span className="block text-[10px] text-muted-foreground line-through">
                          €{item.previousPrice.toFixed(2)}
                        </span>
                      </TableCell>
                      <TableCell className="py-2 text-xs text-right">
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] px-1.5",
                            item.change < 0
                              ? "border-success/30 text-success"
                              : "border-destructive/30 text-destructive"
                          )}
                        >
                          {item.change > 0 ? "+" : ""}{item.change}%
                        </Badge>
                      </TableCell>
                      <TableCell className="py-2 text-[11px] text-right text-muted-foreground">
                        {item.store}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        {/* Heatmap Section */}
        <div className="grid grid-cols-1 mt-6">
          <Card className="bg-surface border-border hover:border-primary/10 transition-colors">
            <CardHeader className="pb-4 border-b border-border/50">
              <div className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full bg-destructive/80 animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
                <CardTitle className="text-sm font-medium text-foreground">
                  Minimum Advertised Price (MAP) Anomaly Heatmap
                </CardTitle>
              </div>
              <p className="text-[11px] text-muted-foreground max-w-2xl leading-relaxed mt-1">
                Visual matrix highlighting stores selling below market median. Dark red cells (less than -15%) indicate severe dumping violations threatening brand positioning.
              </p>
            </CardHeader>
            <CardContent className="pt-6">
              <PriceSpikeHeatmap />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
