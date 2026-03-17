import { Plus } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const stores = ["All", "Douglas", "Notino", "220.lv", "Makeup.lv", "1a.lv"];
const brands = ["Dior", "Hugo Boss", "Versace", "Armani", "Paco Rabanne"];

export default function DashboardFilterBar() {
  const [activeStore, setActiveStore] = useState("All");
  const [activeBrands, setActiveBrands] = useState<string[]>([]);

  const toggleBrand = (b: string) =>
    setActiveBrands((prev) =>
      prev.includes(b) ? prev.filter((x) => x !== b) : [...prev, b]
    );

  const pillBase = "px-3 py-1.5 rounded-full text-[13px] font-medium transition-colors whitespace-nowrap";

  return (
    <div data-tutorial="filters" className="h-12 flex items-center gap-3 px-6 overflow-x-auto scrollbar-hide">
      {/* Store pills */}
      {stores.map((s) => (
        <button
          key={s}
          onClick={() => setActiveStore(s)}
          className={cn(
            pillBase,
            activeStore === s
              ? "bg-primary text-primary-foreground"
              : "bg-surface-2 text-muted-foreground border border-border hover:text-foreground"
          )}
        >
          {s}
        </button>
      ))}

      {/* Divider */}
      <div className="w-px h-5 bg-border shrink-0" />

      {/* Brand pills */}
      {brands.map((b) => (
        <button
          key={b}
          onClick={() => toggleBrand(b)}
          className={cn(
            pillBase,
            activeBrands.includes(b)
              ? "bg-primary text-primary-foreground"
              : "bg-surface-2 text-muted-foreground border border-border hover:text-foreground"
          )}
        >
          {b}
        </button>
      ))}

      {/* Add button */}
      <button
        className={cn(
          pillBase,
          "border border-dashed border-muted-foreground text-muted-foreground hover:text-foreground flex items-center gap-1"
        )}
      >
        <Plus size={12} />
        Add
      </button>
    </div>
  );
}
