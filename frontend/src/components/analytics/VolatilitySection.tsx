import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Package } from "lucide-react";
import { api, VolatilityItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import SectionHeader from "./SectionHeader";
import VolatilityScatter from "./VolatilityScatter";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";

type Window = "7d" | "30d";
const WINDOWS: Window[] = ["7d", "30d"];

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvija$/i, "").trim().slice(0, 2).toUpperCase();
}

export default function VolatilitySection() {
  const navigate = useNavigate();
  const [window, setWindow] = useState<Window>("30d");
  const [items, setItems] = useState<VolatilityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getVolatility(window, 15)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        console.error("Failed to load volatility:", err);
        if (!cancelled) setError("Could not load volatility leaders.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  const maxVol = Math.max(...items.map((i) => i.volatility_eur), 1);

  return (
    <>
      <SectionHeader
        index="05"
        label="Volatility"
        title="Most volatile products"
        description="Standard deviation of price within the window. Useful for picking targets that move enough to be worth alerting on."
        right={
          <div className="flex items-center gap-1 p-0.5 rounded-md border border-border bg-surface">
            {WINDOWS.map((w) => (
              <button
                key={w}
                onClick={() => setWindow(w)}
                className={cn(
                  "px-2.5 py-1 rounded font-mono text-[11px] font-medium tracking-wider transition-colors",
                  window === w ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {w.toUpperCase()}
              </button>
            ))}
          </div>
        }
      />

      {loading ? (
        <LoadingState label="Loading volatility" />
      ) : error ? (
        <ErrorState message={error} />
      ) : items.length === 0 ? (
        <EmptyState message="Not enough price observations in this window." icon={Activity} />
      ) : (
        <div className="flex flex-col gap-4">
          <VolatilityScatter window={window} />
          <div className="border border-border rounded-md bg-surface/40 overflow-hidden divide-y divide-border">
          {items.map((v, i) => {
            const ratio = v.volatility_eur / maxVol;
            return (
              <div
                key={v.product_id}
                onClick={() => navigate(`/product/${v.product_id}`)}
                className="grid grid-cols-[20px_40px_1fr_120px_140px] gap-3 px-4 py-3 items-center hover:bg-surface/60 transition-colors cursor-pointer"
              >
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
                  {String(i + 1).padStart(2, "0")}
                </span>

                <div className="w-9 h-9 rounded-md bg-surface-2 border border-border shrink-0 flex items-center justify-center overflow-hidden">
                  {v.image_url ? (
                    <img
                      src={v.image_url}
                      alt={v.title}
                      className="w-full h-full object-contain p-0.5"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                  ) : (
                    <Package size={12} className="text-muted-foreground/40" strokeWidth={1.25} />
                  )}
                </div>

                <div className="min-w-0">
                  <p className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-muted-foreground truncate">
                    {v.brand ?? "—"} · {storeTag(v.store_name)}
                  </p>
                  <p className="text-[12.5px] text-foreground truncate">{v.title}</p>
                </div>

                <div className="flex flex-col items-end shrink-0 w-[120px]">
                  <span className="font-mono font-semibold tabular-nums text-[13px] text-foreground">
                    {v.current_price.toFixed(2)} €
                  </span>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                    range {v.range_eur.toFixed(2)} €
                  </span>
                </div>

                <div className="flex flex-col gap-1 w-[140px] shrink-0">
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                      σ
                    </span>
                    <span className="font-mono tabular-nums text-[12px] font-semibold text-foreground">
                      {v.volatility_eur.toFixed(2)} €
                    </span>
                  </div>
                  <div className="w-full h-1 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${ratio * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
          </div>
        </div>
      )}
    </>
  );
}
