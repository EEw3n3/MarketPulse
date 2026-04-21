import { ArrowLeft, Upload, Bell, Package } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ProductCardDetail, ProductFeedItem } from "@/lib/api";

interface Props {
  product: ProductCardDetail;
  onExport: () => void;
  onTrack: () => void;
}

const STORE_COLORS: Record<string, string> = {
  "notino":          "bg-[hsl(var(--success))]",
  "notino.lv":       "bg-[hsl(var(--success))]",
  "douglas latvia":  "bg-blue-500",
  "douglas.lv":      "bg-blue-500",
  "makeup.lv":       "bg-pink-500",
  "makeup":          "bg-pink-500",
  "1a.lv":           "bg-orange-500",
  "220.lv":          "bg-amber-500",
};

function storeColor(name: string): string {
  return STORE_COLORS[name.toLowerCase()] ?? "bg-gray-500";
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

export default function ProductInfoColumn({ product, onExport, onTrack }: Props) {
  const navigate = useNavigate();

  const { percent, direction } = calcChange(product.current_price, product.old_price ?? null);

  // Build price comparison rows: main product + competitors, sorted cheapest first
  type StoreRow = { name: string; price: number; dot: string; item?: ProductFeedItem };
  const rows: StoreRow[] = [
    { name: product.store_name, price: product.current_price, dot: storeColor(product.store_name) },
    ...product.competitors.map(c => ({ name: c.storeName, price: c.currentPrice, dot: c.storeColor, item: c })),
  ].sort((a, b) => a.price - b.price);
  if (rows.length) rows[0] = { ...rows[0] };
  const bestPrice = rows[0]?.price;

  return (
    <div className="w-full md:w-[380px] md:h-full flex flex-col md:overflow-y-auto border-b md:border-b-0 md:border-r border-border bg-surface shrink-0 scrollbar-hide">
      <div className="p-6 flex flex-col gap-5">
        {/* Back */}
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-primary transition-colors w-fit"
        >
          <ArrowLeft size={14} />
          All Products
        </button>

        {/* Product image */}
        <div className="w-[320px] h-[320px] mx-auto rounded-card border border-border bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] shadow-[0_0_40px_rgba(124,58,237,0.15)] flex items-center justify-center transition-transform duration-250 ease-brand hover:scale-[1.03] cursor-pointer overflow-hidden">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.title}
              className="w-full h-full object-contain p-4"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <Package className="text-muted-foreground opacity-20" size={80} strokeWidth={1} />
          )}
        </div>

        {/* Brand + Name */}
        <div className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-widest text-muted-foreground">
            {product.brand ?? "—"}
          </span>
          <h1 className="text-[32px] font-bold font-display leading-tight text-foreground">
            {product.title}
          </h1>
        </div>

        {/* Volume / concentration chips */}
        <div className="flex gap-2 flex-wrap">
          {product.volume && (
            <span className="px-3 py-1 rounded-full bg-surface-2 text-[12px] text-muted-foreground">
              {product.volume}
            </span>
          )}
          {product.concentration && (
            <span className="px-3 py-1 rounded-full bg-surface-2 text-[12px] text-muted-foreground">
              {product.concentration}
            </span>
          )}
        </div>

        {/* Current price */}
        <div className="flex items-end gap-3">
          <span className={`text-[48px] font-bold font-display leading-none price-display ${direction === "down" ? "text-[hsl(var(--success))]" : "text-foreground"}`}>
            {product.current_price.toFixed(2)} €
          </span>
        </div>

        {/* Previous price + change badge */}
        {product.old_price && direction !== "none" && (
          <div className="flex items-center gap-2 -mt-2">
            <span className="text-[13px] text-muted-foreground line-through">
              {product.old_price.toFixed(2)} €
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[12px] font-semibold ${
              direction === "down"
                ? "bg-[hsl(var(--success))]/20 text-[hsl(var(--success))]"
                : "bg-destructive/20 text-destructive"
            }`}>
              {direction === "down" ? "↓" : "↑"} {direction === "down" ? "−" : "+"}{percent}%
            </span>
          </div>
        )}

        {/* Cross-site comparison */}
        {rows.length > 0 && (
          <div className="flex flex-col gap-1.5 mt-2">
            <span className="text-[13px] font-semibold text-foreground mb-1">Price Comparison</span>
            {rows.map((s, i) => {
              const isBest = s.price === bestPrice && i === 0;
              return (
                <div
                  key={`${s.name}-${s.price}`}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                    isBest ? "bg-[hsl(var(--success))]/10 border border-[hsl(var(--success))]/20" : "bg-surface-2"
                  }`}
                >
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${s.dot || "bg-gray-500"}`} />
                  <span className="text-[13px] text-foreground flex-1">{s.name}</span>
                  <span className={`text-[13px] font-semibold price-display ${isBest ? "text-[hsl(var(--success))]" : "text-foreground"}`}>
                    {s.price.toFixed(2)} €
                  </span>
                  {isBest && (
                    <span className="text-[11px] text-[hsl(var(--success))] font-semibold">Best ✓</span>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-col gap-2 mt-3">
          <button
            onClick={onExport}
            className="w-full h-11 rounded-button border border-primary text-primary text-[13px] font-semibold flex items-center justify-center gap-2 hover:bg-primary/10 transition-colors"
          >
            <Upload size={15} />
            Export
          </button>
          <button
            onClick={onTrack}
            className="w-full h-11 rounded-button bg-primary text-primary-foreground text-[13px] font-semibold flex items-center justify-center gap-2 shadow-glow hover:brightness-110 transition-all"
          >
            <Bell size={15} />
            Track Price
          </button>
        </div>
      </div>
    </div>
  );
}
