import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Package, ArrowRight } from "lucide-react";
import { api, SpreadItem } from "@/lib/api";
import SectionHeader from "./SectionHeader";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvija$/i, "").trim().slice(0, 2).toUpperCase();
}

export default function SpreadsSection() {
  const navigate = useNavigate();
  const [items, setItems] = useState<SpreadItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getSpreads(20)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        console.error("Failed to load spreads:", err);
        if (!cancelled) setError("Could not load spreads.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <SectionHeader
        index="02"
        label="Arbitrage"
        title="Biggest cross-store spreads"
        description="Same product, different price. Sorted by spread percentage — largest gaps first."
      />

      {loading ? (
        <LoadingState label="Loading spreads" />
      ) : error ? (
        <ErrorState message={error} />
      ) : items.length === 0 ? (
        <EmptyState message="No multi-store spreads detected yet." />
      ) : (
        <div className="border border-border rounded-md bg-surface/40 overflow-hidden divide-y divide-border">
          {items.map((s, i) => (
            <div
              key={s.group_id}
              onClick={() => navigate(`/product/${s.cheapest_product_id}`)}
              className="group grid grid-cols-[20px_44px_1fr_auto] gap-3 px-4 py-3.5 hover:bg-surface/60 transition-colors cursor-pointer items-center"
            >
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
                {String(i + 1).padStart(2, "0")}
              </span>

              <div className="w-11 h-11 rounded-md bg-surface-2 border border-border flex items-center justify-center overflow-hidden">
                {s.image_url ? (
                  <img
                    src={s.image_url}
                    alt={s.name}
                    className="w-full h-full object-contain p-0.5"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : (
                  <Package size={14} className="text-muted-foreground/40" strokeWidth={1.25} />
                )}
              </div>

              <div className="min-w-0">
                <p className="text-[13px] text-foreground truncate font-medium">{s.name}</p>
                <div className="flex items-center gap-2 mt-1 font-mono text-[10.5px] tabular-nums text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-6 h-4 rounded-sm bg-surface-2 border border-border text-[9px] flex items-center justify-center">
                      {storeTag(s.cheapest_store)}
                    </span>
                    <span className="text-[hsl(var(--success))] font-semibold">
                      {s.cheapest_price.toFixed(2)} €
                    </span>
                  </span>
                  <ArrowRight size={10} className="text-muted-foreground/50" />
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-6 h-4 rounded-sm bg-surface-2 border border-border text-[9px] flex items-center justify-center">
                      {storeTag(s.most_expensive_store)}
                    </span>
                    <span className="text-foreground">{s.most_expensive_price.toFixed(2)} €</span>
                  </span>
                  <span className="text-muted-foreground/50">·</span>
                  <span>{s.store_count} stores</span>
                </div>
              </div>

              <div className="flex flex-col items-end shrink-0">
                <span className="font-mono font-semibold tabular-nums text-[15px] text-foreground">
                  +{s.spread_abs.toFixed(2)} €
                </span>
                <span className="font-mono text-[10px] tabular-nums text-[hsl(var(--success))] font-semibold">
                  {s.spread_percent.toFixed(0)}% spread
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
