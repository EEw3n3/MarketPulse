import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, BrandStoreCell } from "@/lib/api";
import SectionHeader from "./SectionHeader";
import { cn } from "@/lib/utils";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvija$/i, "").trim().slice(0, 2).toUpperCase();
}

export default function HeatmapSection() {
  const navigate = useNavigate();
  const [cells, setCells] = useState<BrandStoreCell[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getBrandStoreMatrix(15, 1)
      .then((data) => {
        if (!cancelled) setCells(data);
      })
      .catch((err) => {
        console.error("Failed to load brand-store matrix:", err);
        if (!cancelled) setError("Could not load heatmap.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const { brands, stores, matrix, minAvg, maxAvg } = useMemo(() => {
    const brandSet = new Set<string>();
    const storeSet = new Set<string>();
    const map: Record<string, BrandStoreCell> = {};
    let mn = Infinity;
    let mx = -Infinity;
    for (const c of cells) {
      brandSet.add(c.brand);
      storeSet.add(c.store);
      map[`${c.brand}::${c.store}`] = c;
      if (c.avg_price < mn) mn = c.avg_price;
      if (c.avg_price > mx) mx = c.avg_price;
    }
    return {
      brands: Array.from(brandSet).sort(),
      stores: Array.from(storeSet).sort(),
      matrix: map,
      minAvg: mn === Infinity ? 0 : mn,
      maxAvg: mx === -Infinity ? 0 : mx,
    };
  }, [cells]);

  // teal intensity by avg price within [min, max]
  const intensity = (price: number) => {
    if (maxAvg <= minAvg) return 0.2;
    const t = (price - minAvg) / (maxAvg - minAvg);
    return 0.08 + t * 0.55; // [0.08 .. 0.63]
  };

  return (
    <>
      <SectionHeader
        index="04"
        label="Heatmap"
        title="Brand × Store"
        description="Average price per cell. Top 15 brands by catalog coverage. Darker teal = higher avg price relative to others."
      />

      {loading ? (
        <LoadingState label="Loading heatmap" height="h-[260px]" />
      ) : error ? (
        <ErrorState message={error} />
      ) : cells.length === 0 ? (
        <EmptyState message="Not enough data for a heatmap yet." />
      ) : (
        <div className="border border-border rounded-md bg-surface/40 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="sticky left-0 bg-surface/40 px-4 py-3 text-left font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground w-[160px] z-10">
                  Brand
                </th>
                {stores.map((s) => (
                  <th
                    key={s}
                    className="px-2 py-3 text-center font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground"
                  >
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="w-7 h-5 rounded-sm bg-surface-2 border border-border text-[9px] flex items-center justify-center text-foreground">
                        {storeTag(s)}
                      </span>
                      <span className="text-muted-foreground/70 font-normal text-[9.5px] normal-case tracking-normal max-w-[80px] truncate">
                        {s}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {brands.map((b) => (
                <tr key={b} className="border-t border-border">
                  <td className="sticky left-0 bg-surface/40 px-4 py-2 text-[12.5px] text-foreground truncate w-[160px] z-10">
                    {b}
                  </td>
                  {stores.map((s) => {
                    const cell = matrix[`${b}::${s}`];
                    if (!cell) {
                      return (
                        <td
                          key={s}
                          className="px-2 py-2 text-center font-mono text-[10.5px] text-muted-foreground/30"
                        >
                          ·
                        </td>
                      );
                    }
                    const opacity = intensity(cell.avg_price);
                    return (
                      <td
                        key={s}
                        title={`${b} · ${s} — ${cell.product_count} products, avg ${cell.avg_price.toFixed(2)} €`}
                        className={cn(
                          "px-2 py-2 text-center cursor-pointer transition-colors",
                          "hover:ring-1 hover:ring-primary/40"
                        )}
                        style={{ backgroundColor: `hsl(var(--primary) / ${opacity})` }}
                        onClick={() =>
                          navigate(
                            `/catalog?brands=${encodeURIComponent(b)}&stores=${encodeURIComponent(s)}`
                          )
                        }
                      >
                        <div className="flex flex-col items-center">
                          <span className="font-mono text-[11.5px] tabular-nums font-semibold text-foreground">
                            {cell.avg_price.toFixed(0)}€
                          </span>
                          <span className="font-mono text-[9px] tabular-nums text-muted-foreground">
                            {cell.product_count}
                          </span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
