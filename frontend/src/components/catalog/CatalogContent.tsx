import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Grid3X3,
  List,
  Download,
  ExternalLink,
  X,
  RefreshCw,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import CatalogFilterPanel, { FilterState, defaultFilters } from "./CatalogFilterPanel";

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

const stores = ["All Stores", "Douglas.lv", "Notino.lv", "1a.lv", "Makeup.lv", "220.lv"];
const types = ["All Types", "EDP", "EDT", "Parfum", "Cologne"];
const ROWS_PER_PAGE = 12;

export default function CatalogContent() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [sortField, setSortField] = useState<SortField>("brand");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCatalog = async () => {
      setLoading(true);
      try {
        const queryParams = new URLSearchParams();
        if (filters.search) queryParams.append("search", filters.search);
        filters.brands.forEach(b => queryParams.append("brands", b));
        filters.stores.forEach(s => queryParams.append("stores", s.toLowerCase()));
        queryParams.append("skip", String((page - 1) * ROWS_PER_PAGE));
        queryParams.append("limit", String(ROWS_PER_PAGE));

        const data = await api.getCatalog(queryParams.toString());
        setProducts(data);
      } catch (err) {
        console.error("Failed to load catalog:", err);
      } finally {
        setLoading(false);
      }
    };
    loadCatalog();
  }, [filters, page]);

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

  const totalPages = 5; // Placeholder

  return (
    <div className="flex flex-col gap-0">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <div>
            <h1 className="text-xl font-bold font-display tracking-tight text-foreground">
              Product Catalog
            </h1>
            <p className="text-[13px] text-muted-foreground mt-0.5">
              Live market database
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1.5 text-[13px] bg-surface/50 backdrop-blur-md border border-border shadow-sm hover:bg-surface-2 transition-colors">
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
            placeholder="Search by name, brand..."
            value={filters.search}
            onChange={(e) => { setFilters(p => ({ ...p, search: e.target.value })); setPage(1); }}
            className="pl-9 h-9 text-[13px] bg-surface-2 border-border"
          />
        </div>

        <CatalogFilterPanel
          filters={filters}
          setFilters={(f) => { typeof f === "function" ? setFilters((prev: FilterState) => { const next = f(prev); setPage(1); return next; }) : (() => { setFilters(f); setPage(1); })(); }}
          availableBrands={Array.from(new Set(products.map(p => p.brand)))}
          availableStores={stores.filter(s => s !== "All Stores")}
          availableTypes={types.filter(t => t !== "All Types")}
        />

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

      {/* Loading State */}
      {loading ? (
        <div className="flex flex-col items-center justify-center h-[400px] gap-4">
          <RefreshCw className="animate-spin text-primary" size={32} />
          <p className="text-muted-foreground">Fetching products...</p>
        </div>
      ) : (
        <>
          {viewMode === "table" ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left font-medium px-6 py-3">Brand</th>
                    <th className="text-left font-medium px-3 py-3">Product</th>
                    <th className="text-left font-medium px-3 py-3 w-[80px]">Type</th>
                    <th className="text-right font-medium px-3 py-3 w-[100px]">Price</th>
                    <th className="text-right font-medium px-3 py-3 w-[110px]">Change</th>
                    <th className="text-left font-medium px-3 py-3 w-[120px]">Store</th>
                    <th className="text-center font-medium px-3 py-3 w-[80px]">Status</th>
                    <th className="text-right font-medium px-6 py-3 w-[50px]"></th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => navigate(`/product/${p.id}`)}
                      className="border-b border-border/50 hover:bg-surface-2/50 cursor-pointer transition-colors group"
                    >
                      <td className="px-6 py-3">
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
                      <td className="px-3 py-3 text-right font-display tabular-nums tracking-tight font-semibold text-foreground">
                        {p.price.toFixed(2)} €
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span
                          className={cn(
                            "inline-flex items-center gap-0.5 text-[12px] font-medium font-display tabular-nums tracking-tight",
                            p.changeDirection === "down" ? "text-[hsl(var(--success))]" : "text-destructive"
                          )}
                        >
                          {p.changeDirection === "down" ? "↓" : "↑"}{" "}
                          {p.changePercent.toFixed(1)}%
                        </span>
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
                        <ExternalLink size={14} className="text-muted-foreground/50 group-hover:text-primary transition-colors" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 p-6">
              {products.map((p) => (
                <div
                  key={p.id}
                  onClick={() => navigate(`/product/${p.id}`)}
                  className="rounded-[var(--radius-card)] border border-border bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] p-4 cursor-pointer hover:border-primary/40 hover:-translate-y-1 hover:shadow-[0_12px_32px_rgba(0,0,0,0.4)] transition-all duration-300 group"
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
                    <span className="text-lg font-bold font-display tabular-nums tracking-tight text-foreground">
                      {p.price.toFixed(2)} €
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Pagination */}
      <div className="px-6 py-4 border-t border-border flex items-center justify-between">
        <span className="text-[13px] text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="w-8 h-8 rounded-[var(--radius-button)] flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
