import { Plus, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const stores = ["All", "Douglas", "Notino", "220.lv", "Makeup.lv", "1a.lv"];
const brands = ["Dior", "Hugo Boss", "Versace", "Armani", "Paco Rabanne"];

export default function DashboardFilterBar() {
  const [activeStore, setActiveStore] = useState("All");
  const [activeBrands, setActiveBrands] = useState<string[]>([]);

  const toggleBrand = (b: string) =>
    setActiveBrands((prev) => (prev.includes(b) ? prev.filter((x) => x !== b) : [...prev, b]));

  const chip =
    "inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium transition-colors whitespace-nowrap border";

  return (
    <div
      data-tutorial="filters"
      className="h-12 flex items-center gap-5 px-5 lg:px-7 overflow-x-auto scrollbar-hide border-b border-border bg-background"
    >
      {/* Stores group */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Store
        </span>
        <div className="flex items-center gap-1.5">
          {stores.map((s) => (
            <button
              key={s}
              onClick={() => setActiveStore(s)}
              className={cn(
                chip,
                activeStore === s
                  ? "bg-foreground text-background border-foreground"
                  : "bg-transparent text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="w-px h-5 bg-border shrink-0" />

      {/* Brands group */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Brand
        </span>
        <div className="flex items-center gap-1.5">
          {brands.map((b) => {
            const active = activeBrands.includes(b);
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
          <button
            className={cn(
              chip,
              "border-dashed text-muted-foreground hover:text-foreground hover:border-muted-foreground"
            )}
          >
            <Plus size={11} strokeWidth={2} />
            Add
          </button>
        </div>
      </div>

      <div className="flex-1" />

      {/* More filters */}
      <button className="shrink-0 inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors">
        <SlidersHorizontal size={13} strokeWidth={1.75} />
        More filters
      </button>
    </div>
  );
}
