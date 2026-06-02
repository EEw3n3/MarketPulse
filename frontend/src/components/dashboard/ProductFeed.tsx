import { useRef, useState, useEffect, useLayoutEffect } from "react";
import { ChevronLeft, ChevronRight, Package, ArrowDown, ArrowUp, ArrowUpRight, Heart } from "lucide-react";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state-views";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ProductFeedItem } from "@/lib/api";
import { useFavorites } from "@/contexts/FavoritesContext";
import { useAuth } from "@/contexts/AuthContext";
import { canonicalStore, STORE_OPTIONS } from "@/lib/stores";
import { expandBrandAliases } from "@/lib/brands";

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
  // Taller image area + white background — perfume packshots almost always
  // ship on white, so a white tile blends seamlessly with the product photo
  // and lets the bottle fill the card edge-to-edge.
  const imgHeight = compact ? "h-44" : "h-52";

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
      <div className={`${imgHeight} relative overflow-hidden bg-white border-b border-border flex items-center justify-center`}>
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            className="w-full h-full object-contain p-1"
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

function ScrollableRow({ products, compact = false, scrollKey }: { products: ProductFeedItem[]; compact?: boolean; scrollKey: string }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState(false);
  const restoredOnce = useRef(false);

  // Restore horizontal scroll once products are available, before paint.
  // Persisted in sessionStorage so it survives navigation to a product card
  // and back, but doesn't outlive the browser session.
  useLayoutEffect(() => {
    if (restoredOnce.current || products.length === 0 || !scrollRef.current) return;
    const stored = sessionStorage.getItem(`feedScroll:${scrollKey}`);
    if (stored) {
      const x = parseInt(stored, 10);
      if (!Number.isNaN(x)) scrollRef.current.scrollLeft = x;
    }
    restoredOnce.current = true;
  }, [products.length, scrollKey]);

  // Persist current scrollLeft on every scroll (rAF-throttled).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let raf = 0;
    const handler = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        sessionStorage.setItem(`feedScroll:${scrollKey}`, String(el.scrollLeft));
      });
    };
    el.addEventListener("scroll", handler, { passive: true });
    return () => {
      el.removeEventListener("scroll", handler);
      cancelAnimationFrame(raf);
    };
  }, [scrollKey]);

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

function prioritizeByPreferences(
  items: ProductFeedItem[],
  preferredBrands: string[],
  preferredStores: string[]
): ProductFeedItem[] {
  if (preferredBrands.length === 0 && preferredStores.length === 0) return items;
  // Expand each preferred brand through its aliases so a shorthand preference
  // ("YSL") still matches products stored under the full name
  // ("Yves Saint Laurent"). Without this, alias brands never get prioritized.
  const brandsLower = new Set(preferredBrands.flatMap((b) => expandBrandAliases(b)));
  const storesLower = new Set(preferredStores.map((s) => s.toLowerCase()));
  const score = (p: ProductFeedItem) => {
    const brandMatch = brandsLower.has(p.brand.toLowerCase()) ? 2 : 0;
    const storeMatch = storesLower.has(p.storeName.toLowerCase()) ? 1 : 0;
    return brandMatch + storeMatch;
  };
  return [...items].sort((a, b) => score(b) - score(a));
}

export default function ProductFeed() {
  const [products, setProducts] = useState<ProductFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  const preferredBrands = user?.preferences?.interested_brands ?? [];
  const preferredStores = user?.preferences?.monitored_stores ?? [];

  // Filter values come from the URL (?stores=&brands=&search=) so they survive
  // reloads and stay in sync with DashboardFilterBar / DashboardTopBar.
  const filterStores = searchParams.getAll("stores");
  const filterBrands = searchParams.getAll("brands");
  const filterSearch = searchParams.get("search") ?? "";

  useEffect(() => {
    const loadFeed = async () => {
      try {
        setLoading(true);
        // Each store gets its OWN top-50 by last_seen DESC. Without per-store
        // calls a single global feed?limit=N is dominated by whichever store
        // was scraped most recently (Makeup's ingest gave 10k recent rows),
        // so other-store sections appear empty under any filter.
        //
        // We fan out one call per store (~5) in parallel via Promise.all,
        // each scoped to that store's canonical key + same brand/search
        // filters. Results are flattened and the existing
        // group-by-store grouping below handles the rest.
        const storeKeysToQuery = filterStores.length > 0
          ? filterStores
          : STORE_OPTIONS.map((s) => s.key);

        const results = await Promise.all(
          storeKeysToQuery.map((storeKey) =>
            api.getFeed({
              limit: 50,
              stores: [storeKey],
              brands: filterBrands.length > 0 ? filterBrands : undefined,
              search: filterSearch || undefined,
            })
          )
        );
        const data = results.flat();
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
    // searchParams.toString() — stable dep that re-runs when any param changes
  }, [searchParams.toString()]); // eslint-disable-line react-hooks/exhaustive-deps

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

  if (products.length === 0) {
    return (
      <EmptyState
        message="No products match your filters."
        description="Adjust the store, brand, or search filters above."
        icon={Package}
        className="h-[400px] border-0 rounded-none bg-transparent"
      />
    );
  }

  // Apply preference-based prioritization before grouping
  const prioritized = prioritizeByPreferences(products, preferredBrands, preferredStores);

  // Group by store
  const byStore = prioritized.reduce<Record<string, ProductFeedItem[]>>((acc, p) => {
    const key = p.storeName ?? "Other";
    (acc[key] ??= []).push(p);
    return acc;
  }, {});
  // Preferred stores appear first in the section order
  const storesLowerSet = new Set(preferredStores.map((s) => s.toLowerCase()));
  const storeOrder = Object.keys(byStore).sort((a, b) => {
    const aPreferred = storesLowerSet.has(a.toLowerCase()) ? 1 : 0;
    const bPreferred = storesLowerSet.has(b.toLowerCase()) ? 1 : 0;
    if (bPreferred !== aPreferred) return bPreferred - aPreferred;
    return byStore[b].length - byStore[a].length;
  });

  const droppedCount = prioritized.filter((p) => p.changeDirection === "down").length;
  const increasedCount = prioritized.filter((p) => p.changeDirection === "up").length;

  return (
    <div className="flex flex-col gap-10 px-5 lg:px-7 pt-7 pb-10">
      {/* Status strip */}
      <div className="flex items-center justify-between flex-wrap gap-y-2">
        <div className="flex items-center gap-6 text-[12px]">
          <span className="font-mono text-muted-foreground">
            Updated {timeStr} · {prioritized.length} changes tracked
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

      {/* Latest changes — main row. Hidden when the user has filtered down to a
          single store, since the per-store section below would be an exact
          duplicate. */}
      {storeOrder.length !== 1 && (
        <section>
          <SectionHeader
            eyebrow="01 · Activity"
            title="Latest changes"
            count={prioritized.length}
          />
          <ScrollableRow products={prioritized} scrollKey="latest" />
        </section>
      )}

      {/* Per-store sections */}
      {storeOrder.map((store, idx) => (
        <section key={store}>
          <SectionHeader
            // When "Latest changes" is hidden (single-store filter), this
            // section becomes 01 — otherwise it shifts down to 02+.
            eyebrow={`0${storeOrder.length === 1 ? idx + 1 : idx + 2} · ${store}`}
            title={`Movements on ${store}`}
            count={byStore[store].length}
            cta={{ label: "See all", onClick: () => navigate(`/catalog?stores=${encodeURIComponent(canonicalStore(store))}`) }}
          />
          <ScrollableRow products={byStore[store]} compact scrollKey={`store-${store}`} />
        </section>
      ))}
    </div>
  );
}
