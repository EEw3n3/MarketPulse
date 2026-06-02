import { Plus, SlidersHorizontal, Check, X, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { BRAND_OPTIONS, QUICK_PICK_BRANDS } from "@/lib/brands";
import { STORE_OPTIONS } from "@/lib/stores";
import { useAuth } from "@/contexts/AuthContext";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const chip =
  "inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium transition-colors whitespace-nowrap border";

// Once-per-browser-session guard so the onboarding store pre-select only
// applies on the user's first Dashboard visit of the session — after that
// the user's manual filter choices (including "All") are respected.
const PREFS_APPLIED_KEY = "mp_dashboard_prefs_applied";

export default function DashboardFilterBar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [brandSheetOpen, setBrandSheetOpen] = useState(false);
  const [brandSearch, setBrandSearch] = useState("");

  const selectedStores = searchParams.getAll("stores");
  const selectedBrands = searchParams.getAll("brands");

  // Pre-select the user's monitored stores from onboarding the first time they
  // land on the Dashboard. monitored_stores already holds canonical keys
  // ("douglas", "notino") matching STORE_OPTIONS[].key and the ?stores= URL
  // format, so no conversion is needed. The STORE chips and ProductFeed both
  // read ?stores from the URL, so they pick this up automatically.
  useEffect(() => {
    const prefStores = user?.preferences?.monitored_stores ?? [];
    if (prefStores.length === 0) return;
    // Don't override an existing filter or re-apply within the same session.
    const hasUrlFilters =
      searchParams.has("stores") || searchParams.has("brands") || searchParams.has("search");
    if (hasUrlFilters) return;
    if (sessionStorage.getItem(PREFS_APPLIED_KEY)) return;
    sessionStorage.setItem(PREFS_APPLIED_KEY, "1");
    const next = new URLSearchParams(searchParams);
    prefStores.forEach((s) => next.append("stores", s));
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const updateParam = (key: "stores" | "brands", values: string[]) => {
    const next = new URLSearchParams(searchParams);
    next.delete(key);
    values.forEach((v) => next.append(key, v));
    setSearchParams(next, { replace: true });
  };

  const toggleStore = (key: string) => {
    const next = selectedStores.includes(key)
      ? selectedStores.filter((s) => s !== key)
      : [...selectedStores, key];
    updateParam("stores", next);
  };

  const toggleBrand = (brand: string) => {
    const next = selectedBrands.includes(brand)
      ? selectedBrands.filter((b) => b !== brand)
      : [...selectedBrands, brand];
    updateParam("brands", next);
  };

  const clearAll = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("stores");
    next.delete("brands");
    setSearchParams(next, { replace: true });
  };

  const filteredBrands = useMemo(() => {
    const q = brandSearch.trim().toLowerCase();
    if (!q) return BRAND_OPTIONS;
    return BRAND_OPTIONS.filter((b) => b.toLowerCase().includes(q));
  }, [brandSearch]);

  // Quick-pick chips: union of QUICK_PICK_BRANDS + any selected brand not in the list
  const visibleBrandChips = useMemo(() => {
    const set = new Set([...QUICK_PICK_BRANDS, ...selectedBrands]);
    return Array.from(set);
  }, [selectedBrands]);

  const allStoresSelected = selectedStores.length === 0;

  return (
    <div
      data-tutorial="filters"
      className="h-12 flex items-center gap-5 px-5 lg:px-7 overflow-x-auto scrollbar-hide border-b border-border bg-background"
    >
      {/* Stores group — multi-select */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Store
        </span>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => updateParam("stores", [])}
            className={cn(
              chip,
              allStoresSelected
                ? "bg-foreground text-background border-foreground"
                : "bg-transparent text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
            )}
          >
            All
          </button>
          {STORE_OPTIONS.map(({ label, key }) => {
            const active = selectedStores.includes(key);
            return (
              <button
                key={key}
                onClick={() => toggleStore(key)}
                className={cn(
                  chip,
                  active
                    ? "bg-surface text-foreground border-primary/60"
                    : "bg-transparent text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
                )}
              >
                {active && <span className="w-1 h-1 rounded-full bg-primary" />}
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="w-px h-5 bg-border shrink-0" />

      {/* Brands group */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Brand
        </span>
        <div className="flex items-center gap-1.5">
          {visibleBrandChips.map((b) => {
            const active = selectedBrands.includes(b);
            return (
              <button
                key={b}
                onClick={() => toggleBrand(b)}
                className={cn(
                  chip,
                  active
                    ? "bg-surface text-foreground border-primary/60"
                    : "bg-transparent text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
                )}
              >
                {active && <span className="w-1 h-1 rounded-full bg-primary" />}
                {b}
              </button>
            );
          })}
          <Sheet open={brandSheetOpen} onOpenChange={setBrandSheetOpen}>
            <SheetTrigger asChild>
              <button className={cn(chip, "border-dashed text-muted-foreground hover:text-foreground hover:border-muted-foreground")}>
                <Plus size={11} strokeWidth={2} />
                Add
              </button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[340px] sm:w-[400px] p-0 flex flex-col">
              <SheetHeader className="px-5 py-4 border-b border-border">
                <SheetTitle className="font-['Inter'] text-[15px] font-semibold">Pick brands</SheetTitle>
              </SheetHeader>
              <div className="px-5 py-3 border-b border-border">
                <div className="relative">
                  <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    value={brandSearch}
                    onChange={(e) => setBrandSearch(e.target.value)}
                    placeholder="Search brands..."
                    className="w-full h-9 pl-9 pr-3 rounded-md bg-surface border border-border text-[13px] text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-3">
                <div className="grid grid-cols-2 gap-1.5">
                  {filteredBrands.map((b) => {
                    const active = selectedBrands.includes(b);
                    return (
                      <button
                        key={b}
                        onClick={() => toggleBrand(b)}
                        className={cn(
                          "flex items-center justify-between gap-2 px-2.5 py-2 rounded-md border text-left text-[12.5px] transition-colors",
                          active
                            ? "bg-surface border-primary/60 text-foreground"
                            : "bg-transparent border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground"
                        )}
                      >
                        <span className="truncate">{b}</span>
                        {active && <Check size={12} className="text-primary shrink-0" strokeWidth={2.5} />}
                      </button>
                    );
                  })}
                </div>
                {filteredBrands.length === 0 && (
                  <p className="text-[12px] text-muted-foreground text-center py-6">
                    No brands match "{brandSearch}"
                  </p>
                )}
              </div>
              <div className="px-5 py-3 border-t border-border flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  {selectedBrands.length} selected
                </span>
                <button
                  onClick={() => updateParam("brands", [])}
                  className="text-[12px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear
                </button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      <div className="flex-1" />

      {/* Active-filter clear shortcut */}
      {(selectedStores.length > 0 || selectedBrands.length > 0) && (
        <button
          onClick={clearAll}
          className="shrink-0 inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
        >
          <X size={12} strokeWidth={2} />
          Clear
        </button>
      )}

      {/* More filters — placeholder, opens the same sheet for now */}
      <button
        onClick={() => setBrandSheetOpen(true)}
        className="shrink-0 inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
      >
        <SlidersHorizontal size={13} strokeWidth={1.75} />
        More filters
      </button>
    </div>
  );
}
