import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, CatalogItem } from "@/lib/api";
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Grid3X3,
  List,
  Download,
  ArrowUpRight,
  Package,
} from "lucide-react";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";
import { cn } from "@/lib/utils";
import CatalogFilterPanel, { FilterState, defaultFilters } from "./CatalogFilterPanel";

type SortField = "brand" | "name" | "price" | "change" | "store";
type SortDir = "asc" | "desc";

const stores = ["Douglas.lv", "Notino.lv", "1a.lv", "Makeup.lv", "220.lv"];
const types = ["EDP", "EDT", "Parfum", "Cologne"];
const ROWS_PER_PAGE = 12;

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvia$/i, "").trim().slice(0, 2).toUpperCase();
}

function ChangePill({ direction, percent }: { direction: "up" | "down" | "none"; percent: number }) {
  if (direction === "none") {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[10px] font-medium text-muted-foreground px-1.5 py-0.5 rounded bg-surface-2/70 border border-border">
        · flat
      </span>
    );
  }
  const isDown = direction === "down";
  const Icon = isDown ? ArrowDown : ArrowUp;
  const tone = isDown ? "text-[hsl(var(--success))]" : "text-destructive";
  const border = isDown ? "border-[hsl(var(--success))]/30" : "border-destructive/30";
  const bg = isDown ? "bg-[hsl(var(--success))]/[0.08]" : "bg-destructive/[0.08]";
  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded ${tone} ${border} ${bg} border`}
    >
      <Icon size={9} strokeWidth={2.75} />
      {isDown ? "−" : "+"}
      {percent.toFixed(1)}%
    </span>
  );
}

export default function CatalogContent() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Filter state lives in URL params — shared with DashboardTopBar (search) and
  // DashboardFilterBar (brands/stores). Local state only holds UI-only values
  // (sort, viewMode, page) and supplemental filter fields not yet in the URL
  // (priceRange, types, inStock).
  const [extraFilters, setExtraFilters] = useState<Pick<FilterState, "types" | "priceRange" | "inStock">>({
    types: defaultFilters.types,
    priceRange: defaultFilters.priceRange,
    inStock: defaultFilters.inStock,
  });

  const filters: FilterState = useMemo(() => ({
    search: searchParams.get("search") ?? "",
    brands: searchParams.getAll("brands"),
    stores: searchParams.getAll("stores"),
    types: extraFilters.types,
    priceRange: extraFilters.priceRange,
    inStock: extraFilters.inStock,
  }), [searchParams, extraFilters]);

  const setFilters: React.Dispatch<React.SetStateAction<FilterState>> = (updater) => {
    const next = typeof updater === "function" ? (updater as (p: FilterState) => FilterState)(filters) : updater;
    // URL-bound fields. Stores are already canonical keys (lowercase, no .lv) —
    // CatalogFilterPanel canonicalizes before adding/removing. Don't double-process.
    const params = new URLSearchParams(searchParams);
    params.delete("search");
    params.delete("brands");
    params.delete("stores");
    params.set("page", "1"); // reset page on any filter change
    if (next.search) params.set("search", next.search);
    next.brands.forEach((b) => params.append("brands", b));
    next.stores.forEach((s) => params.append("stores", s));
    setSearchParams(params, { replace: true });
    // Extra (non-URL) fields
    setExtraFilters({ types: next.types, priceRange: next.priceRange, inStock: next.inStock });
  };

  const [sortField, setSortField] = useState<SortField>("brand");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");
  const [products, setProducts] = useState<CatalogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [allBrands, setAllBrands] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // page lives in URL so back-navigation restores position
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10));
  const setPage = (p: number | ((prev: number) => number)) => {
    const next = typeof p === "function" ? p(page) : p;
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("page", String(next));
      return params;
    }, { replace: true });
  };

  // Fetch the complete list of brands once — the filter panel needs all of them,
  // not just the brands present on the current page.
  useEffect(() => {
    let cancelled = false;
    api.getBrands()
      .then(rows => { if (!cancelled) setAllBrands(rows.map(r => r.name)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const buildFilterParams = () => {
    const p = new URLSearchParams();
    if (filters.search) p.append("search", filters.search);
    filters.brands.forEach(b => p.append("brands", b));
    filters.stores.forEach(s => p.append("stores", s));
    return p;
  };

  // Re-fetch total count whenever filters change (not on page change)
  useEffect(() => {
    let cancelled = false;
    const filterParams = buildFilterParams();
    api.getCatalogCount(filterParams.toString())
      .then(res => { if (!cancelled) setTotal(res.total); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [filters.search, filters.brands.join(","), filters.stores.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const queryParams = buildFilterParams();
    queryParams.append("skip", String((page - 1) * ROWS_PER_PAGE));
    queryParams.append("limit", String(ROWS_PER_PAGE));

    api.getCatalog(queryParams.toString())
      .then(data => { if (!cancelled) setProducts(data); })
      .catch(err => {
        console.error("Failed to load catalog:", err);
        if (!cancelled) setError(err?.message ?? "Could not load catalog.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [filters.search, filters.brands.join(","), filters.stores.join(","), page]); // eslint-disable-line react-hooks/exhaustive-deps

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
    if (sortField !== field) return <ArrowUpDown size={11} className="text-muted-foreground/40" />;
    return sortDir === "asc" ? (
      <ArrowUp size={11} className="text-foreground" />
    ) : (
      <ArrowDown size={11} className="text-foreground" />
    );
  };

  const totalPages = Math.max(1, Math.ceil(total / ROWS_PER_PAGE));

  const headerCell = (
    label: string,
    field?: SortField,
    align: "left" | "right" | "center" = "left",
    extraClass = ""
  ) => (
    <th
      className={cn(
        "font-mono text-[10px] uppercase tracking-[0.14em] font-medium text-muted-foreground py-3 px-3",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        extraClass
      )}
    >
      {field ? (
        <button
          onClick={() => toggleSort(field)}
          className={cn(
            "inline-flex items-center gap-1.5 hover:text-foreground transition-colors",
            align === "right" && "ml-auto",
            align === "center" && "mx-auto"
          )}
        >
          {label}
          <SortIcon field={field} />
        </button>
      ) : (
        label
      )}
    </th>
  );

  return (
    <div className="flex flex-col gap-0">
      {/* Header */}
      <div className="px-5 lg:px-7 pt-7 pb-5 border-b border-border">
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
              00 · Catalog
            </p>
            <div className="flex items-baseline gap-3">
              <h1 className="font-['Inter'] font-semibold text-foreground text-[22px] tracking-[-0.01em]">
                Product database
              </h1>
              <span className="font-mono tabular-nums text-[12px] text-muted-foreground">
                {total.toLocaleString()} {total === 1 ? "row" : "rows"}
              </span>
            </div>
          </div>
          <button className="inline-flex items-center gap-1.5 h-9 px-3 rounded-md border border-border text-muted-foreground text-[12.5px] font-medium hover:text-foreground hover:border-muted-foreground transition-colors">
            <Download size={13} strokeWidth={1.75} />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="px-5 lg:px-7 py-3 border-b border-border flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px] max-w-[360px]">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by name, brand…"
            value={filters.search}
            onChange={(e) => { setFilters(p => ({ ...p, search: e.target.value })); }}
            className="w-full h-9 pl-9 pr-3 rounded-md bg-surface border border-border text-[13px] text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
          />
        </div>

        <CatalogFilterPanel
          filters={filters}
          setFilters={setFilters}
          availableBrands={allBrands.length > 0 ? allBrands : Array.from(new Set(products.map(p => p.brand)))}
          availableStores={stores}
          availableTypes={types}
        />

        {/* View toggle */}
        <div className="ml-auto flex items-center gap-0.5 p-0.5 rounded-md border border-border bg-surface">
          <button
            onClick={() => setViewMode("table")}
            className={cn(
              "w-7 h-7 rounded flex items-center justify-center transition-colors",
              viewMode === "table" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
            )}
            aria-label="Table view"
          >
            <List size={13} />
          </button>
          <button
            onClick={() => setViewMode("grid")}
            className={cn(
              "w-7 h-7 rounded flex items-center justify-center transition-colors",
              viewMode === "grid" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
            )}
            aria-label="Grid view"
          >
            <Grid3X3 size={13} />
          </button>
        </div>
      </div>

      {/* Loading / Error / Empty / Data */}
      {loading ? (
        <LoadingState
          label="Fetching products"
          className="h-[400px] border-0 rounded-none bg-transparent"
        />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={() => setFilters({ ...filters })}
          className="h-[400px] border-0 rounded-none bg-transparent"
        />
      ) : products.length === 0 ? (
        <EmptyState
          message="No products match your filters."
          description="Adjust search or filter criteria."
          icon={Package}
          className="h-[400px] border-0 rounded-none bg-transparent"
        />
      ) : (
        <>
          {viewMode === "table" ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border bg-surface/40">
                    {headerCell("Brand", "brand", "left", "px-5 lg:px-7 w-[140px]")}
                    {headerCell("Product", "name")}
                    <th className="font-mono text-[10px] uppercase tracking-[0.14em] font-medium text-muted-foreground py-3 px-3 text-left w-[72px]">
                      Type
                    </th>
                    {headerCell("Price", "price", "right", "w-[110px]")}
                    {headerCell("Change", "change", "right", "w-[110px]")}
                    {headerCell("Store", "store", "left", "w-[140px]")}
                    <th className="font-mono text-[10px] uppercase tracking-[0.14em] font-medium text-muted-foreground py-3 px-3 text-center w-[96px]">
                      Status
                    </th>
                    <th className="w-[36px]"></th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => navigate(`/product/${p.id}`)}
                      className="border-b border-border/60 hover:bg-surface/40 cursor-pointer transition-colors group"
                    >
                      <td className="px-5 lg:px-7 py-3">
                        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground font-medium">
                          {p.brand}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span className="text-foreground">{p.name}</span>
                        {p.volume && p.volume !== "N/A" && (
                          <span className="text-muted-foreground ml-2 font-mono tabular-nums text-[11.5px]">
                            {p.volume}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground px-1.5 py-0.5 rounded bg-surface-2 border border-border">
                          {p.type}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right font-mono tabular-nums font-semibold text-foreground">
                        {p.price.toFixed(2)} €
                      </td>
                      <td className="px-3 py-3 text-right">
                        <ChangePill
                          direction={(p.changeDirection as "up" | "down" | "none") ?? "none"}
                          percent={p.changePercent}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <span className="w-7 h-5 rounded-sm bg-surface-2 border border-border font-mono text-[9px] font-medium text-muted-foreground flex items-center justify-center shrink-0">
                            {storeTag(p.store)}
                          </span>
                          <span className="text-[12.5px] text-foreground">{p.store}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 font-mono text-[10px] font-medium uppercase tracking-[0.1em] px-1.5 py-0.5 rounded border",
                            p.in_stock
                              ? "text-[hsl(var(--success))] border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/[0.08]"
                              : "text-muted-foreground border-border bg-surface-2"
                          )}
                        >
                          <span
                            className={cn(
                              "w-1 h-1 rounded-full",
                              p.in_stock ? "bg-[hsl(var(--success))]" : "bg-muted-foreground"
                            )}
                          />
                          {p.in_stock ? "In stock" : "OOS"}
                        </span>
                      </td>
                      <td className="px-5 lg:px-7 py-3 text-right">
                        <ArrowUpRight
                          size={13}
                          className="text-muted-foreground/40 group-hover:text-foreground transition-colors"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 p-5 lg:p-7">
              {products.map((p) => (
                <div
                  key={p.id}
                  onClick={() => navigate(`/product/${p.id}`)}
                  className="group relative rounded-md border border-border bg-surface hover:border-muted-foreground/50 transition-colors p-4 cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground font-medium truncate">
                      {p.brand}
                    </span>
                    <span className="w-6 h-4 rounded-sm bg-surface-2 border border-border font-mono text-[9px] font-medium text-muted-foreground flex items-center justify-center shrink-0 ml-2">
                      {storeTag(p.store)}
                    </span>
                  </div>
                  <p className="text-[12.5px] text-foreground line-clamp-2 leading-snug min-h-[34px] mb-1">
                    {p.name}
                  </p>
                  <p className="font-mono text-[10px] tabular-nums text-muted-foreground mb-3">
                    {p.volume && p.volume !== "N/A" ? `${p.volume} · ` : ""}{p.type}
                  </p>
                  <div className="flex items-end justify-between">
                    <span className="font-mono font-semibold tabular-nums tracking-tight text-[16px] text-foreground">
                      {p.price.toFixed(2)} €
                    </span>
                    <ChangePill
                      direction={(p.changeDirection as "up" | "down" | "none") ?? "none"}
                      percent={p.changePercent}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Pagination */}
      <div className="px-5 lg:px-7 py-4 border-t border-border flex items-center justify-between">
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          Page {page} <span className="text-muted-foreground/50">/ {totalPages}</span>
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1}
            className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-muted-foreground disabled:opacity-30 disabled:hover:text-muted-foreground disabled:hover:border-border transition-colors"
            title="First page"
          >
            <ChevronsLeft size={14} />
          </button>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-muted-foreground disabled:opacity-30 disabled:hover:text-muted-foreground disabled:hover:border-border transition-colors"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-muted-foreground disabled:opacity-30 disabled:hover:text-muted-foreground disabled:hover:border-border transition-colors"
          >
            <ChevronRight size={14} />
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages}
            className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-muted-foreground disabled:opacity-30 disabled:hover:text-muted-foreground disabled:hover:border-border transition-colors"
            title="Last page"
          >
            <ChevronsRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
