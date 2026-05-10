import { ArrowLeft, Upload, Bell, BellRing, Package, ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ProductCardDetail } from "@/lib/api";
import { useFavorites } from "@/contexts/FavoritesContext";
import { useAuth } from "@/contexts/AuthContext";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";

interface Props {
  product: ProductCardDetail;
  onExport: () => void;
  onTrack?: () => void;  // deprecated — Track button now toggles favorite directly
}

function storeTag(name: string): string {
  const cleaned = name.replace(/\.lv$/i, "").replace(/\s+latvia$/i, "").trim();
  return cleaned.slice(0, 2).toUpperCase();
}

function calcChange(current: number, old: number | null): { percent: number; direction: "up" | "down" | "none" } {
  if (!old || old === 0) return { percent: 0, direction: "none" };
  const diff = current - old;
  if (Math.abs(diff) < 0.01) return { percent: 0, direction: "none" };
  return {
    percent: Math.round(Math.abs(diff) / old * 100),
    direction: diff > 0 ? "up" : "down",
  };
}

export default function ProductInfoColumn({ product, onExport }: Props) {
  const navigate = useNavigate();
  const { isFavorite, toggleFavorite } = useFavorites();
  const { user } = useAuth();
  const fav = isFavorite(product.id);

  const handleTrack = async () => {
    const wasTracking = fav;
    await toggleFavorite(product.id);
    if (!wasTracking) {
      const channels = user?.preferences?.notification_channels ?? [];
      if (channels.length > 0) {
        const labels = channels.map((c) => (c === "telegram" ? "Telegram" : "Email")).join(" + ");
        toast.success(`Tracking. Alerts via ${labels}.`);
      } else {
        toast("Tracking.", {
          description: "Configure alert channels in Settings to receive notifications.",
          action: { label: "Settings", onClick: () => navigate("/settings") },
        });
      }
    }
  };

  const { percent, direction } = calcChange(product.current_price, product.old_price ?? null);

  // Backend already returns offers deduplicated by store, sorted by price ASC, max 5.
  const offers = product.offers ?? [];
  const currentStoreNorm = product.store_name.toLowerCase().replace(/\.lv$/, "").replace(/\s+latvia$/, "").trim();
  const bestPrice = offers[0]?.price;
  const worstPrice = offers[offers.length - 1]?.price;
  const spreadPct =
    offers.length > 1 && bestPrice > 0
      ? Math.round(((worstPrice - bestPrice) / bestPrice) * 100)
      : 0;

  return (
    <div className="w-full md:w-[380px] md:h-full flex flex-col md:overflow-y-auto border-b md:border-b-0 md:border-r border-border bg-background shrink-0 scrollbar-hide">
      <div className="p-6 flex flex-col gap-6">
        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors w-fit"
        >
          <ArrowLeft size={13} strokeWidth={1.75} />
          All products
        </button>

        {/* Product image */}
        <div className="w-full aspect-square rounded-md border border-border bg-surface flex items-center justify-center overflow-hidden">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.title}
              className="w-full h-full object-contain p-6"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <Package className="text-muted-foreground/30" size={64} strokeWidth={1} />
          )}
        </div>

        {/* Brand + Name */}
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            {product.brand ?? "—"}
          </span>
          <h1 className="font-['Inter'] font-semibold text-foreground text-[22px] leading-[1.25] tracking-[-0.01em]">
            {product.title}
          </h1>
        </div>

        {/* Volume / concentration chips */}
        {(product.volume || product.concentration) && (
          <div className="flex gap-1.5 flex-wrap">
            {product.volume && (
              <span className="px-2 py-1 rounded-md bg-surface-2 border border-border font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {product.volume}
              </span>
            )}
            {product.concentration && (
              <span className="px-2 py-1 rounded-md bg-surface-2 border border-border font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {product.concentration}
              </span>
            )}
          </div>
        )}

        {/* Current price block */}
        <div className="flex flex-col gap-1.5 pt-1">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Current · {product.store_name}
          </span>
          <div className="flex items-baseline gap-3 flex-wrap">
            <span
              className={`font-mono font-semibold tabular-nums tracking-tight text-[40px] leading-none ${
                direction === "down" ? "text-[hsl(var(--success))]" : "text-foreground"
              }`}
            >
              {product.current_price.toFixed(2)} €
            </span>
            {product.old_price && direction !== "none" && (
              <>
                <span className="font-mono tabular-nums text-[13px] text-muted-foreground line-through">
                  {product.old_price.toFixed(2)}
                </span>
                <span
                  className={`inline-flex items-center gap-1 font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
                    direction === "down"
                      ? "text-[hsl(var(--success))] border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/[0.08]"
                      : "text-destructive border-destructive/30 bg-destructive/[0.08]"
                  }`}
                >
                  {direction === "down" ? (
                    <ArrowDown size={9} strokeWidth={2.75} />
                  ) : (
                    <ArrowUp size={9} strokeWidth={2.75} />
                  )}
                  {direction === "down" ? "−" : "+"}
                  {percent}%
                </span>
              </>
            )}
          </div>
        </div>

        {/* Cross-site comparison */}
        {offers.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                Price comparison · {offers.length} {offers.length === 1 ? "store" : "stores"}
              </span>
              {spreadPct > 0 && (
                <span className="font-mono tabular-nums text-[10px] text-muted-foreground">
                  spread {spreadPct}%
                </span>
              )}
            </div>
            <div className="border border-border rounded-md divide-y divide-border overflow-hidden bg-surface">
              {offers.map((o, i) => {
                const isBest = i === 0 && offers.length > 1;
                const hasVariants = o.variants.length > 0;
                const isCurrentStore =
                  o.storeName.toLowerCase().replace(/\.lv$/, "").replace(/\s+latvia$/, "").trim() === currentStoreNorm;
                const totalCount = 1 + o.variants.length;

                const row = (
                  <div
                    className={`relative flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-surface-2/40 transition-colors ${
                      isBest ? "bg-[hsl(var(--success))]/[0.06]" : ""
                    } ${isCurrentStore ? "border-l-2 border-primary/40 pl-[10px]" : ""}`}
                    // replace:true keeps the history stack flat — chained store
                    // hops (Notino → 1a.lv → Makeup) all collapse, so the back
                    // button always returns to the originating Dashboard/Catalog.
                    onClick={() => !hasVariants && navigate(`/product/${o.product_id}`, { replace: true })}
                  >
                    {hasVariants && (
                      <span className="absolute top-1 right-1 font-mono text-[9px] font-semibold text-primary bg-primary/[0.15] border border-primary/40 rounded px-1 leading-none py-0.5">
                        +{o.variants.length}
                      </span>
                    )}
                    <span className="w-8 h-6 rounded-sm bg-surface-2 border border-border font-mono text-[10px] font-medium text-muted-foreground flex items-center justify-center shrink-0">
                      {storeTag(o.storeName)}
                    </span>
                    <span className="text-[12.5px] text-foreground flex-1 truncate">
                      {o.storeName}
                    </span>
                    <span
                      className={`font-mono tabular-nums font-semibold text-[13px] ${
                        isBest ? "text-[hsl(var(--success))]" : "text-foreground"
                      }`}
                    >
                      {o.price.toFixed(2)} €
                    </span>
                    {isBest && !hasVariants && (
                      <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[hsl(var(--success))] font-semibold">
                        Best
                      </span>
                    )}
                  </div>
                );

                if (!hasVariants) {
                  return <div key={`${o.storeName}-${i}`}>{row}</div>;
                }

                return (
                  <Popover key={`${o.storeName}-${i}`}>
                    <PopoverTrigger asChild>{row}</PopoverTrigger>
                    <PopoverContent side="left" align="start" className="w-[280px] p-2">
                      <div className="flex items-baseline justify-between px-2 pb-2 border-b border-border">
                        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                          {o.storeName}
                        </span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {totalCount} listings
                        </span>
                      </div>
                      <div className="divide-y divide-border">
                        <a
                          href={o.url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center justify-between gap-2 px-2 py-2 hover:bg-surface-2/60 rounded-sm"
                        >
                          <span className="text-[12px] text-foreground truncate flex items-center gap-1.5">
                            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[hsl(var(--success))]">
                              Best
                            </span>
                            Listing #1
                            <ExternalLink size={10} className="text-muted-foreground" />
                          </span>
                          <span className="font-mono tabular-nums text-[12px] text-[hsl(var(--success))] font-semibold shrink-0">
                            {o.price.toFixed(2)} €
                          </span>
                        </a>
                        {o.variants.map((v, vi) => (
                          <a
                            key={v.product_id}
                            href={v.url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center justify-between gap-2 px-2 py-2 hover:bg-surface-2/60 rounded-sm"
                          >
                            <span className="text-[12px] text-foreground truncate flex items-center gap-1">
                              Listing #{vi + 2}
                              <ExternalLink size={10} className="text-muted-foreground" />
                            </span>
                            <span className="font-mono tabular-nums text-[12px] text-foreground shrink-0">
                              {v.price.toFixed(2)} €
                            </span>
                          </a>
                        ))}
                      </div>
                    </PopoverContent>
                  </Popover>
                );
              })}
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-col gap-2 mt-1">
          <button
            onClick={handleTrack}
            className={`w-full h-10 rounded-md text-[12.5px] font-medium flex items-center justify-center gap-2 transition-colors ${
              fav
                ? "border border-primary/40 text-primary bg-primary/[0.08] hover:bg-primary/[0.12]"
                : "bg-foreground text-background hover:bg-foreground/90"
            }`}
            aria-label={fav ? "Stop tracking price" : "Track price"}
          >
            {fav ? (
              <>
                <BellRing size={14} strokeWidth={2} />
                Tracking
              </>
            ) : (
              <>
                <Bell size={14} strokeWidth={2} />
                Track price
              </>
            )}
          </button>
          <button
            onClick={onExport}
            className="w-full h-10 rounded-md border border-border text-muted-foreground text-[12.5px] font-medium flex items-center justify-center gap-2 hover:text-foreground hover:border-muted-foreground transition-colors"
          >
            <Upload size={14} strokeWidth={1.75} />
            Export CSV
          </button>
        </div>
      </div>
    </div>
  );
}
