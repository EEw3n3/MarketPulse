import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, Package } from "lucide-react";
import { api, MoverItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import SectionHeader from "./SectionHeader";
import MoversHistogram from "./MoversHistogram";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";

type Window = "24h" | "7d" | "30d";
const WINDOWS: Window[] = ["24h", "7d", "30d"];

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvija$/i, "").trim().slice(0, 2).toUpperCase();
}

function MoverRow({ item, index }: { item: MoverItem; index: number }) {
  const navigate = useNavigate();
  const isDown = item.direction === "down";

  return (
    <div
      onClick={() => navigate(`/product/${item.product_id}`)}
      className="group flex items-center gap-3 px-4 py-3 hover:bg-surface/40 transition-colors cursor-pointer border-b border-border last:border-b-0"
    >
      <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60 w-5 shrink-0">
        {String(index + 1).padStart(2, "0")}
      </span>

      <div className="w-9 h-9 rounded-md bg-surface-2 border border-border shrink-0 flex items-center justify-center overflow-hidden">
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={item.title}
            className="w-full h-full object-contain p-0.5"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <Package size={12} className="text-muted-foreground/40" strokeWidth={1.25} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-muted-foreground font-medium truncate">
          {item.brand ?? "—"}
        </p>
        <p className="text-[12.5px] text-foreground truncate">{item.title}</p>
      </div>

      <span className="hidden sm:inline-flex w-7 h-5 rounded-sm bg-surface-2 border border-border font-mono text-[9px] font-medium text-muted-foreground items-center justify-center shrink-0">
        {storeTag(item.store_name)}
      </span>

      <div className="flex flex-col items-end shrink-0 w-[110px]">
        <span
          className={cn(
            "font-mono font-semibold tabular-nums text-[13px]",
            isDown ? "text-[hsl(var(--success))]" : "text-foreground"
          )}
        >
          {item.current_price.toFixed(2)} €
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 font-mono text-[10px] font-semibold tabular-nums",
            isDown ? "text-[hsl(var(--success))]" : "text-destructive"
          )}
        >
          {isDown ? <ArrowDown size={9} strokeWidth={2.75} /> : <ArrowUp size={9} strokeWidth={2.75} />}
          {isDown ? "" : "+"}
          {item.change_percent.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export default function MoversSection() {
  const [window, setWindow] = useState<Window>("7d");
  const [items, setItems] = useState<MoverItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getMovers(window, 30, "both")
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        console.error("Failed to load movers:", err);
        if (!cancelled) setError("Could not load movers.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  const drops = items.filter((i) => i.direction === "down").slice(0, 10);
  const rises = items.filter((i) => i.direction === "up").slice(0, 10);

  return (
    <>
      <SectionHeader
        index="01"
        label="Movers"
        title="Top price movers"
        description="Biggest winners and losers across the catalog within the selected window."
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
        <LoadingState label="Loading movers" />
      ) : error ? (
        <ErrorState message={error} />
      ) : items.length === 0 ? (
        <EmptyState message="No tracked movements in this window." />
      ) : (
        <div className="flex flex-col gap-4">
          <MoversHistogram window={window} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Drops */}
          <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
            <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--success))]">
                ↓ Drops
              </span>
              <span className="font-mono tabular-nums text-[11px] text-muted-foreground">
                {drops.length}
              </span>
            </div>
            {drops.length === 0 ? (
              <div className="px-4 py-6 text-[12.5px] text-muted-foreground">No price drops in this window.</div>
            ) : (
              drops.map((m, i) => <MoverRow key={m.product_id} item={m} index={i} />)
            )}
          </div>

          {/* Rises */}
          <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
            <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-destructive">
                ↑ Rises
              </span>
              <span className="font-mono tabular-nums text-[11px] text-muted-foreground">
                {rises.length}
              </span>
            </div>
            {rises.length === 0 ? (
              <div className="px-4 py-6 text-[12.5px] text-muted-foreground">No price rises in this window.</div>
            ) : (
              rises.map((m, i) => <MoverRow key={m.product_id} item={m} index={i} />)
            )}
          </div>
          </div>
        </div>
      )}
    </>
  );
}

