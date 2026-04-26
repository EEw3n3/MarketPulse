import { useRef, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Package, ArrowDown, ArrowUp, ArrowUpRight, Heart } from "lucide-react";
import { LoadingState, ErrorState } from "@/components/ui/state-views";
import { useNavigate } from "react-router-dom";
import { api, ProductFeedItem } from "@/lib/api";
import { useFavorites } from "@/contexts/FavoritesContext";

function ChangeBadge({ direction, percent }: { direction: "up" | "down" | "none"; percent: number }) {
  if (direction === "none") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-mono font-medium text-muted-foreground px-1.5 py-0.5 rounded bg-surface-2/70 border border-border">
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
      className={`inline-flex items-center gap-1 text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${tone} ${border} ${bg} border`}
    >
      <Icon size={9} strokeWidth={2.75} />
      {isDown ? "−" : "+"}
      {percent}%
    </span>
  );
}

function ProductCard({ product, compact = false }: { product: ProductFeedItem; compact?: boolean }) {
  const navigate = useNavigate();
  const { isFavorite, toggleFavorite } = useFavorites();
  const width = compact ? "w-48" : "w-[220px]";
  const imgHeight = compact ? "h-28" : "h-36";

  const handleClick = () => navigate(`/product/${product.id}`);
  const fav = isFavorite(product.id);

  const isDown = product.changeDirection === "down";

  return (
    <div
      onClick={handleClick}
      className={`${width} shrink-0 group relative rounded-lg border border-border bg-surface hover:border-muted-foreground/50 transition-colors overflow-hidden cursor-pointer`}
      style={{ scrollSnapAlign: "start" }}
      {...(!compact && product.id === 1 ? { "data-tutorial": "product-card" } : {})}
    >
      {/* Image area */}
      <div className={`${imgHeight} relative overflow-hidden bg-surface-2 border-b border-border flex items-center justify-center`}>
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            className="w-full h-full object-contain p-3"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <Package className="text-muted-foreground/40" size={compact ? 28 : 36} strokeWidth={1.25} />
        )}

        {/* Store tag */}
        <span className="absolute top-2 left-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground bg-background/90 border border-border px-1.5 py-0.5 rounded">
          {product.storeInitial}
        </span>

        {/* Change badge */}
        <div className="absolute top-2 right-2">
          <ChangeBadge direction={product.changeDirection} percent={product.changePercent} />
        </div>

        {/* Favorite heart */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleFavorite(product.id);
          }}
          className={`absolute bottom-2 left-2 w-7 h-7 rounded-md flex items-center justify-center transition-all ${
            fav
              ? "bg-background/90 border border-border text-primary opacity-100"
              : "bg-background/80 border border-border text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-foreground"
          }`}
          aria-label={fav ? "Remove from favorites" : "Add to favorites"}
        >
          <Heart size={13} strokeWidth={1.75} fill={fav ? "currentColor" : "none"} />
        </button>
      </div>

      {/* Body */}
      <div className="p-3 flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground font-medium truncate">
          {product.brand}
        </span>
        <span className={`${compact ? "text-[12px]" : "text-[13px]"} font-medium text-foreground line-clamp-2 leading-snug min-h-[34px]`}>
          {product.title}
        </span>
        <div className="flex items-baseline gap-2 mt-1">
          <span
            className={`font-mono font-semibold tabular-nums tracking-tight ${compact ? "text-[16px]" : "text-[18px]"} ${
              isDown ? "text-[hsl(var(--success))]" : "text-foreground"
            }`}
          >
            {product.currentPrice.toFixed(2)} €
          </span>
          {product.previousPrice !== product.currentPrice && (
            <span className="text-[11px] text-muted-foreground line-through tabular-nums font-mono">
              {product.previousPrice.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Hover arrow */}
      <div className="absolute bottom-2 right-2 w-6 h-6 rounded-md bg-background/0 group-hover:bg-foreground group-hover:text-background text-muted-foreground flex items-center justify-center transition-colors opacity-0 group-hover:opacity-100">
        <ArrowUpRight size={12} strokeWidth={2} />
      </div>
    </div>
  );
}

function ScrollableRow({ products, compact = false }: { products: ProductFeedItem[]; compact?: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState(false);

  const scroll = (dir: "left" | "right") => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir === "left" ? -240 : 240, behavior: "smooth" });
  };

  return (
    <div className="relative" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div
        ref={scrollRef}
        className="flex gap-3 overflow-x-auto scrollbar-hide pb-1"
        style={{ scrollSnapType: "x mandatory" }}
      >
        {products.map((p) => (
          <ProductCard key={p.id} product={p} compact={compact} />
        ))}
      </div>

      {hovered && products.length > 4 && (
        <>
          <button
            onClick={() => scroll("left")}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-2 w-8 h-8 rounded-md bg-background border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground flex items-center justify-center transition-colors z-10"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            onClick={() => scroll("right")}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-2 w-8 h-8 rounded-md bg-background border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground flex items-center justify-center transition-colors z-10"
          >
            <ChevronRight size={14} />
          </button>
        </>
      )}
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  count,
  cta,
}: {
  eyebrow: string;
  title: string;
  count?: number;
  cta?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex items-end justify-between mb-4">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
          {eyebrow}
        </p>
        <div className="flex items-baseline gap-2.5">
          <h2 className="font-['Inter'] font-semibold text-foreground text-[18px] tracking-[-0.01em]">
            {title}
          </h2>
          {count !== undefined && (
            <span className="font-mono text-[12px] text-muted-foreground">{count}</span>
          )}
        </div>
      </div>
      {cta && (
        <button
          onClick={cta.onClick}
          className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
        >
          {cta.label}
          <ArrowUpRight size={12} />
        </button>
      )}
    </div>
  );
}

export default function ProductFeed() {
  const [products, setProducts] = useState<ProductFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadFeed = async () => {
      try {
        setLoading(true);
        const data = await api.getFeed();
        setProducts(data);
        setError(null);
      } catch (err) {
        console.error("Failed to load product feed:", err);
        setError("Could not load latest changes. Please try again later.");
      } finally {
        setLoading(false);
      }
    };
    loadFeed();
  }, []);

  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

  if (loading) {
    return (
      <LoadingState
        label="Loading feed"
        className="h-[400px] border-0 rounded-none bg-transparent"
      />
    );
  }

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => window.location.reload()}
        className="h-[400px] border-0 rounded-none bg-transparent"
      />
    );
  }

  // Group by store
  const byStore = products.reduce<Record<string, ProductFeedItem[]>>((acc, p) => {
    const key = p.storeName ?? "Other";
    (acc[key] ??= []).push(p);
    return acc;
  }, {});
  const storeOrder = Object.keys(byStore).sort((a, b) => byStore[b].length - byStore[a].length);

  const droppedCount = products.filter((p) => p.changeDirection === "down").length;
  const increasedCount = products.filter((p) => p.changeDirection === "up").length;

  return (
    <div className="flex flex-col gap-10 px-5 lg:px-7 pt-7 pb-10">
      {/* Status strip */}
      <div className="flex items-center justify-between flex-wrap gap-y-2">
        <div className="flex items-center gap-6 text-[12px]">
          <span className="font-mono text-muted-foreground">
            Updated {timeStr} · {products.length} changes tracked
          </span>
          <span className="flex items-center gap-1.5 text-[hsl(var(--success))]">
            <ArrowDown size={11} strokeWidth={2.5} />
            <span className="font-mono tabular-nums">{droppedCount}</span>
            <span className="text-muted-foreground">dropped</span>
          </span>
          <span className="flex items-center gap-1.5 text-destructive">
            <ArrowUp size={11} strokeWidth={2.5} />
            <span className="font-mono tabular-nums">{increasedCount}</span>
            <span className="text-muted-foreground">increased</span>
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="relative flex w-1.5 h-1.5">
            <span className="absolute inline-flex w-full h-full rounded-full bg-[hsl(var(--success))] opacity-75 animate-ping" />
            <span className="relative inline-flex w-1.5 h-1.5 rounded-full bg-[hsl(var(--success))]" />
          </span>
          <span className="font-mono uppercase tracking-[0.1em]">Live</span>
        </div>
      </div>

      {/* Latest changes — main row */}
      <section>
        <SectionHeader
          eyebrow="01 · Activity"
          title="Latest changes"
          count={products.length}
        />
        <ScrollableRow products={products} />
      </section>

      {/* Per-store sections */}
      {storeOrder.map((store, idx) => (
        <section key={store}>
          <SectionHeader
            eyebrow={`0${idx + 2} · ${store}`}
            title={`Movements on ${store}`}
            count={byStore[store].length}
            cta={{ label: "See all", onClick: () => navigate(`/catalog?store=${encodeURIComponent(store)}`) }}
          />
          <ScrollableRow products={byStore[store]} compact />
        </section>
      ))}
    </div>
  );
}
