import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  SlidersHorizontal,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Grid3X3,
  List,
  Download,
  ExternalLink,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ───── Types ─────
type SortField = "brand" | "name" | "price" | "change" | "store";
type SortDir = "asc" | "desc";

type CatalogProduct = {
  id: number;
  sku: string;
  brand: string;
  name: string;
  volume: string;
  type: string;
  price: number;
  previousPrice: number;
  changePercent: number;
  changeDirection: "up" | "down" | "none";
  store: string;
  storeColor: string;
  inStock: boolean;
  lastUpdated: string;
};

// ───── Mock data ─────
const catalogData: CatalogProduct[] = [
  { id: 1, sku: "DIO-SAU-100", brand: "DIOR", name: "Sauvage Eau de Parfum", volume: "100 ml", type: "EDP", price: 125.00, previousPrice: 135.00, changePercent: 7.41, changeDirection: "down", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-23" },
  { id: 2, sku: "HUG-BOT-200", brand: "HUGO BOSS", name: "Boss Bottled Eau de Parfum", volume: "200 ml", type: "EDP", price: 89.99, previousPrice: 85.00, changePercent: 5.87, changeDirection: "up", store: "Notino.lv", storeColor: "bg-[hsl(var(--success))]", inStock: true, lastUpdated: "2026-03-23" },
  { id: 3, sku: "VER-ERO-100", brand: "VERSACE", name: "Eros Eau de Toilette", volume: "100 ml", type: "EDT", price: 72.50, previousPrice: 82.00, changePercent: 11.59, changeDirection: "down", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-22" },
  { id: 4, sku: "ARM-ADG-075", brand: "ARMANI", name: "Acqua di Giò Profondo", volume: "75 ml", type: "EDP", price: 98.00, previousPrice: 92.00, changePercent: 6.52, changeDirection: "up", store: "1a.lv", storeColor: "bg-orange-500", inStock: true, lastUpdated: "2026-03-23" },
  { id: 5, sku: "PAC-1MI-100", brand: "PACO RABANNE", name: "1 Million Parfum", volume: "100 ml", type: "Parfum", price: 79.99, previousPrice: 95.00, changePercent: 15.80, changeDirection: "down", store: "Makeup.lv", storeColor: "bg-pink-500", inStock: true, lastUpdated: "2026-03-21" },
  { id: 6, sku: "LAC-L12-100", brand: "LACOSTE", name: "L.12.12 Blanc Eau de Toilette", volume: "100 ml", type: "EDT", price: 54.50, previousPrice: 52.00, changePercent: 4.81, changeDirection: "up", store: "Notino.lv", storeColor: "bg-[hsl(var(--success))]", inStock: false, lastUpdated: "2026-03-20" },
  { id: 7, sku: "MON-EXP-100", brand: "MONTBLANC", name: "Explorer Eau de Parfum", volume: "100 ml", type: "EDP", price: 62.00, previousPrice: 70.00, changePercent: 11.43, changeDirection: "down", store: "220.lv", storeColor: "bg-amber-500", inStock: true, lastUpdated: "2026-03-22" },
  { id: 8, sku: "GIV-GEN-100", brand: "GIVENCHY", name: "Gentleman Society Eau de Parfum", volume: "100 ml", type: "EDP", price: 105.00, previousPrice: 110.00, changePercent: 4.55, changeDirection: "down", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-23" },
  { id: 9, sku: "DIO-MIS-100", brand: "DIOR", name: "Miss Dior Blooming Bouquet", volume: "100 ml", type: "EDT", price: 99.00, previousPrice: 112.00, changePercent: 11.61, changeDirection: "down", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-22" },
  { id: 10, sku: "CHA-BLE-100", brand: "CHANEL", name: "Bleu de Chanel Eau de Parfum", volume: "100 ml", type: "EDP", price: 139.00, previousPrice: 135.00, changePercent: 2.96, changeDirection: "up", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-23" },
  { id: 11, sku: "YSL-LIB-090", brand: "YSL", name: "Libre Intense Eau de Parfum", volume: "90 ml", type: "EDP", price: 108.50, previousPrice: 120.00, changePercent: 9.58, changeDirection: "down", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-21" },
  { id: 12, sku: "VAL-DON-100", brand: "VALENTINO", name: "Donna Born In Roma", volume: "100 ml", type: "EDP", price: 95.00, previousPrice: 89.00, changePercent: 6.74, changeDirection: "up", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: false, lastUpdated: "2026-03-20" },
  { id: 13, sku: "VER-DYL-100", brand: "VERSACE", name: "Dylan Blue Eau de Toilette", volume: "100 ml", type: "EDT", price: 58.00, previousPrice: 68.00, changePercent: 14.71, changeDirection: "down", store: "Notino.lv", storeColor: "bg-[hsl(var(--success))]", inStock: true, lastUpdated: "2026-03-22" },
  { id: 14, sku: "ARM-STR-100", brand: "ARMANI", name: "Stronger With You Intensely", volume: "100 ml", type: "EDP", price: 82.00, previousPrice: 78.00, changePercent: 5.13, changeDirection: "up", store: "Notino.lv", storeColor: "bg-[hsl(var(--success))]", inStock: true, lastUpdated: "2026-03-23" },
  { id: 15, sku: "HUG-SCE-100", brand: "HUGO BOSS", name: "The Scent Eau de Parfum", volume: "100 ml", type: "EDP", price: 67.99, previousPrice: 75.00, changePercent: 9.35, changeDirection: "down", store: "Notino.lv", storeColor: "bg-[hsl(var(--success))]", inStock: true, lastUpdated: "2026-03-21" },
  { id: 16, sku: "PRA-LUN-100", brand: "PRADA", name: "Luna Rossa Carbon", volume: "100 ml", type: "EDT", price: 88.00, previousPrice: 84.00, changePercent: 4.76, changeDirection: "up", store: "Notino.lv", storeColor: "bg-[hsl(var(--success))]", inStock: true, lastUpdated: "2026-03-23" },
  { id: 17, sku: "TOM-OUD-050", brand: "TOM FORD", name: "Oud Wood Eau de Parfum", volume: "50 ml", type: "EDP", price: 195.00, previousPrice: 195.00, changePercent: 0, changeDirection: "none", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-23" },
  { id: 18, sku: "BVL-MAN-100", brand: "BVLGARI", name: "Man In Black Eau de Parfum", volume: "100 ml", type: "EDP", price: 76.50, previousPrice: 85.00, changePercent: 10.00, changeDirection: "down", store: "1a.lv", storeColor: "bg-orange-500", inStock: true, lastUpdated: "2026-03-22" },
  { id: 19, sku: "CRE-AVE-100", brand: "CREED", name: "Aventus Eau de Parfum", volume: "100 ml", type: "EDP", price: 320.00, previousPrice: 310.00, changePercent: 3.23, changeDirection: "up", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-23" },
  { id: 20, sku: "JMN-WOO-100", brand: "JO MALONE", name: "Wood Sage & Sea Salt", volume: "100 ml", type: "Cologne", price: 112.00, previousPrice: 118.00, changePercent: 5.08, changeDirection: "down", store: "Douglas.lv", storeColor: "bg-blue-500", inStock: true, lastUpdated: "2026-03-21" },
];

const stores = ["All Stores", "Douglas.lv", "Notino.lv", "1a.lv", "Makeup.lv", "220.lv"];
const types = ["All Types", "EDP", "EDT", "Parfum", "Cologne"];
const stockFilters = ["All", "In Stock", "Out of Stock"];

const ROWS_PER_PAGE = 12;

export default function CatalogContent() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [storeFilter, setStoreFilter] = useState("All Stores");
  const [typeFilter, setTypeFilter] = useState("All Types");
  const [stockFilter, setStockFilter] = useState("All");
  const [sortField, setSortField] = useState<SortField>("brand");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
    setPage(1);
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown size={13} className="text-muted-foreground/50" />;
    return sortDir === "asc" ? (
      <ArrowUp size={13} className="text-primary" />
    ) : (
      <ArrowDown size={13} className="text-primary" />
    );
  };

  const filtered = useMemo(() => {
    let data = [...catalogData];

    if (search) {
      const q = search.toLowerCase();
      data = data.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.brand.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q)
      );
    }
    if (storeFilter !== "All Stores") data = data.filter((p) => p.store === storeFilter);
    if (typeFilter !== "All Types") data = data.filter((p) => p.type === typeFilter);
    if (stockFilter === "In Stock") data = data.filter((p) => p.inStock);
    if (stockFilter === "Out of Stock") data = data.filter((p) => !p.inStock);

    data.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "brand": cmp = a.brand.localeCompare(b.brand); break;
        case "name": cmp = a.name.localeCompare(b.name); break;
        case "price": cmp = a.price - b.price; break;
        case "change": cmp = a.changePercent - b.changePercent; break;
        case "store": cmp = a.store.localeCompare(b.store); break;
      }
      return sortDir === "desc" ? -cmp : cmp;
    });

    return data;
  }, [search, storeFilter, typeFilter, stockFilter, sortField, sortDir]);

  const totalPages = Math.ceil(filtered.length / ROWS_PER_PAGE);
  const paginated = filtered.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE);

  return (
    <div className="flex flex-col gap-0">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <div>
            <h1 className="text-xl font-bold font-['Outfit',sans-serif] text-foreground">
              Product Catalog
            </h1>
            <p className="text-[13px] text-muted-foreground mt-0.5">
              {filtered.length} products across {new Set(catalogData.map((p) => p.store)).size} stores
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1.5 text-[13px] border-border">
              <Download size={14} />
              Export
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="px-6 py-3 border-b border-border flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px] max-w-[360px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, brand, or SKU..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-9 h-9 text-[13px] bg-surface-2 border-border"
          />
        </div>

        <Select value={storeFilter} onValueChange={(v) => { setStoreFilter(v); setPage(1); }}>
          <SelectTrigger className="w-[150px] h-9 text-[13px] bg-surface-2 border-border">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {stores.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1); }}>
          <SelectTrigger className="w-[130px] h-9 text-[13px] bg-surface-2 border-border">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {types.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={stockFilter} onValueChange={(v) => { setStockFilter(v); setPage(1); }}>
          <SelectTrigger className="w-[130px] h-9 text-[13px] bg-surface-2 border-border">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {stockFilters.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>

        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setViewMode("table")}
            className={cn(
              "w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center transition-colors",
              viewMode === "table" ? "bg-primary/20 text-primary" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <List size={16} />
          </button>
          <button
            onClick={() => setViewMode("grid")}
            className={cn(
              "w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center transition-colors",
              viewMode === "grid" ? "bg-primary/20 text-primary" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Grid3X3 size={16} />
          </button>
        </div>
      </div>

      {/* Table */}
      {viewMode === "table" ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left font-medium px-6 py-3 w-[100px]">
                  <button onClick={() => toggleSort("brand")} className="flex items-center gap-1.5 hover:text-foreground transition-colors">
                    SKU <SortIcon field="brand" />
                  </button>
                </th>
                <th className="text-left font-medium px-3 py-3">
                  <button onClick={() => toggleSort("brand")} className="flex items-center gap-1.5 hover:text-foreground transition-colors">
                    Brand <SortIcon field="brand" />
                  </button>
                </th>
                <th className="text-left font-medium px-3 py-3">
                  <button onClick={() => toggleSort("name")} className="flex items-center gap-1.5 hover:text-foreground transition-colors">
                    Product <SortIcon field="name" />
                  </button>
                </th>
                <th className="text-left font-medium px-3 py-3 w-[80px]">Type</th>
                <th className="text-right font-medium px-3 py-3 w-[100px]">
                  <button onClick={() => toggleSort("price")} className="flex items-center gap-1.5 justify-end hover:text-foreground transition-colors ml-auto">
                    Price <SortIcon field="price" />
                  </button>
                </th>
                <th className="text-right font-medium px-3 py-3 w-[110px]">
                  <button onClick={() => toggleSort("change")} className="flex items-center gap-1.5 justify-end hover:text-foreground transition-colors ml-auto">
                    Change <SortIcon field="change" />
                  </button>
                </th>
                <th className="text-left font-medium px-3 py-3 w-[120px]">
                  <button onClick={() => toggleSort("store")} className="flex items-center gap-1.5 hover:text-foreground transition-colors">
                    Store <SortIcon field="store" />
                  </button>
                </th>
                <th className="text-center font-medium px-3 py-3 w-[80px]">Status</th>
                <th className="text-right font-medium px-6 py-3 w-[50px]"></th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/product/${p.id}`)}
                  className="border-b border-border/50 hover:bg-surface-2/50 cursor-pointer transition-colors group"
                >
                  <td className="px-6 py-3 font-mono text-muted-foreground text-[12px]">{p.sku}</td>
                  <td className="px-3 py-3">
                    <span className="text-[11px] uppercase tracking-widest text-muted-foreground font-medium">
                      {p.brand}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <div>
                      <span className="font-medium text-foreground group-hover:text-primary transition-colors">
                        {p.name}
                      </span>
                      <span className="text-muted-foreground ml-2">{p.volume}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant="secondary" className="text-[11px] font-normal bg-surface-2 text-muted-foreground border-0">
                      {p.type}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-right font-['Outfit',sans-serif] font-semibold text-foreground">
                    {p.price.toFixed(2)} €
                  </td>
                  <td className="px-3 py-3 text-right">
                    {p.changeDirection === "none" ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <span
                        className={cn(
                          "inline-flex items-center gap-0.5 text-[12px] font-medium",
                          p.changeDirection === "down" ? "text-[hsl(var(--success))]" : "text-destructive"
                        )}
                      >
                        {p.changeDirection === "down" ? "↓" : "↑"}{" "}
                        {p.changeDirection === "down" ? "−" : "+"}
                        {p.changePercent.toFixed(1)}%
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-1.5">
                      <div className={cn("w-2 h-2 rounded-full shrink-0", p.storeColor)} />
                      <span className="text-foreground">{p.store}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <Badge
                      variant="secondary"
                      className={cn(
                        "text-[11px] font-normal border-0",
                        p.inStock
                          ? "bg-[hsl(var(--success))]/15 text-[hsl(var(--success))]"
                          : "bg-destructive/15 text-destructive"
                      )}
                    >
                      {p.inStock ? "In Stock" : "OOS"}
                    </Badge>
                  </td>
                  <td className="px-6 py-3 text-right">
                    <ExternalLink
                      size={14}
                      className="text-muted-foreground/50 group-hover:text-primary transition-colors"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        /* Grid view */
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 p-6">
          {paginated.map((p) => (
            <div
              key={p.id}
              onClick={() => navigate(`/product/${p.id}`)}
              className="rounded-[var(--radius-card)] border border-border bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] p-4 cursor-pointer hover:border-primary/30 transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">
                  {p.brand}
                </span>
                <div className={cn("w-2 h-2 rounded-full", p.storeColor)} />
              </div>
              <p className="text-[13px] font-medium text-foreground line-clamp-2 mb-1 group-hover:text-primary transition-colors">
                {p.name}
              </p>
              <p className="text-[11px] text-muted-foreground mb-3">{p.volume} · {p.type}</p>
              <div className="flex items-end justify-between">
                <span className="text-lg font-bold font-['Outfit',sans-serif] text-foreground">
                  {p.price.toFixed(2)} €
                </span>
                {p.changeDirection !== "none" && (
                  <span
                    className={cn(
                      "text-[11px] font-medium",
                      p.changeDirection === "down" ? "text-[hsl(var(--success))]" : "text-destructive"
                    )}
                  >
                    {p.changeDirection === "down" ? "↓−" : "↑+"}
                    {p.changePercent.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-4 border-t border-border flex items-center justify-between">
          <span className="text-[13px] text-muted-foreground">
            Showing {(page - 1) * ROWS_PER_PAGE + 1}–{Math.min(page * ROWS_PER_PAGE, filtered.length)} of{" "}
            {filtered.length} products
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={cn(
                  "w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center text-[13px] font-medium transition-colors",
                  page === p
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
                )}
              >
                {p}
              </button>
            ))}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
