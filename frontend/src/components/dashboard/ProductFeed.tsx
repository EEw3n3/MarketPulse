import { useRef, useState, useEffect } from "react";
import { RefreshCw, ChevronLeft, ChevronRight, Package, AlertCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, ProductFeedItem } from "@/lib/api";

function ProductCard({ product, small = false }: { product: ProductFeedItem; small?: boolean }) {
  const navigate = useNavigate();
  const [clicking, setClicking] = useState(false);
  const width = small ? "w-48" : "w-[220px]";
  const height = small ? "h-64" : "h-[300px]";
  const imgHeight = small ? "h-24" : "h-40";
  const priceSize = small ? "text-lg" : "text-2xl";

  const handleClick = () => {
    setClicking(true);
    setTimeout(() => navigate(`/product/${product.id}`), 100);
  };

  return (
    <div
      onClick={handleClick}
      className={`${width} ${height} flex-none scroll-snap-align-start group relative rounded-xl border border-border bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_16px_40px_rgba(0,0,0,0.6)] overflow-hidden cursor-pointer ${clicking ? "animate-card-click" : ""}`}
      style={{ scrollSnapAlign: "start" }}
      {...(!small && product.id === 1 ? { "data-tutorial": "product-card" } : {})}
    >
      <div className={`${imgHeight} bg-surface-2 relative overflow-hidden rounded-t-xl flex items-center justify-center`}>
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            className="w-full h-full object-contain p-2"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
          />
        ) : (
          <Package className="text-muted-foreground opacity-20" size={small ? 32 : 48} strokeWidth={1.5} />
        )}
        <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-white flex items-center justify-center shadow-sm">
          <span className="text-[9px] font-bold text-[hsl(240,50%,14%)]">{product.storeInitial}</span>
        </div>
        <div
          className={`absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[11px] font-bold ${product.changeDirection === "down"
              ? "bg-[hsl(var(--success))]/20 text-[hsl(var(--success))] animate-price-glow-green"
              : product.changeDirection === "up"
                ? "bg-destructive/20 text-destructive animate-price-glow-red"
                : "bg-muted text-muted-foreground"
            }`}
        >
          {product.changeDirection === "down" ? "↓" : product.changeDirection === "up" ? "↑" : "•"} {product.changeDirection !== "none" ? (product.changeDirection === "down" ? "−" : "+") : ""}
          {product.changePercent}%
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-background/95 via-background/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end justify-center pb-4">
          <span className="text-primary-foreground text-sm font-semibold translate-y-2 group-hover:translate-y-0 transition-transform duration-300">Learn More →</span>
        </div>
      </div>
      <div className={`${small ? "p-2" : "p-3"} flex flex-col gap-1`}>
        <span className="text-[11px] uppercase tracking-widest text-muted-foreground">{product.brand}</span>
        <span className={`${small ? "text-xs" : "text-[13px]"} font-semibold text-foreground line-clamp-2`}>{product.title}</span>
        <span className={`${priceSize} font-bold font-display tabular-nums tracking-tight ${product.changeDirection === "down" ? "text-[hsl(var(--success))]" : "text-foreground"}`}>
          {product.currentPrice.toFixed(2)} €
        </span>
        <span className="text-[11px] text-muted-foreground line-through tabular-nums">{product.previousPrice.toFixed(2)} €</span>
      </div>
    </div>
  );
}

function ScrollableRow({ products, small = false }: { products: ProductFeedItem[]; small?: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showArrows, setShowArrows] = useState(false);

  const scroll = (dir: "left" | "right") => {
    if (!scrollRef.current) return;
    const amount = dir === "left" ? -240 : 240;
    scrollRef.current.scrollBy({ left: amount, behavior: "smooth" });
  };

  return (
    <div
      className="relative"
      onMouseEnter={() => setShowArrows(true)}
      onMouseLeave={() => setShowArrows(false)}
    >
      <div
        ref={scrollRef}
        className="flex gap-4 overflow-x-auto scrollbar-hide pb-2"
        style={{ scrollSnapType: "x mandatory" }}
      >
        {products.map((p) => (
          <ProductCard key={p.id} product={p} small={small} />
        ))}
      </div>

      {/* Arrows */}
      {showArrows && (
        <>
          <button
            onClick={() => scroll("left")}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-2 w-9 h-9 rounded-full bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] border border-border flex items-center justify-center text-foreground hover:bg-primary/20 transition-colors z-10"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => scroll("right")}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-2 w-9 h-9 rounded-full bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] border border-border flex items-center justify-center text-foreground hover:bg-primary/20 transition-colors z-10"
          >
            <ChevronRight size={18} />
          </button>
        </>
      )}
    </div>
  );
}

function StoreSection({ name, dotColor, products }: { name: string; dotColor: string; products: ProductFeedItem[] }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${dotColor}`} />
          <span className="text-[15px] font-bold text-foreground">{name}</span>
        </div>
        <button className="text-[13px] text-primary hover:underline">See All →</button>
      </div>
      <ScrollableRow products={products} small />
    </div>
  );
}

export default function ProductFeed() {
  const [products, setProducts] = useState<ProductFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const douglasProductFeedItems = products.filter(p => p.storeName?.toLowerCase() === "douglas.lv");
  const notinoProductFeedItems = products.filter(p => p.storeName?.toLowerCase() === "notino.lv");

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[400px] gap-4">
        <RefreshCw className="animate-spin text-primary" size={32} />
        <p className="text-muted-foreground animate-pulse">Loading real-time market data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[400px] gap-4 px-6 text-center">
        <AlertCircle className="text-destructive" size={32} />
        <p className="text-foreground font-medium">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between px-4 md:px-6 pt-6 pb-3">
        <h2 className="text-lg font-bold font-display tracking-tight text-foreground">Latest Changes</h2>
        <div className="flex items-center gap-1 text-[13px] text-muted-foreground">
          <RefreshCw size={14} />
          Live Update
        </div>
      </div>

      {/* Main carousel */}
      <div className="px-4 md:px-6">
        <ScrollableRow products={products} />
      </div>

      {/* Per-store sections */}
      <div className="px-4 md:px-6 flex flex-col gap-8 pb-6">
        {douglasProductFeedItems.length > 0 && (
          <StoreSection name="Douglas.lv" dotColor="bg-blue-500" products={douglasProductFeedItems} />
        )}
        {notinoProductFeedItems.length > 0 && (
          <StoreSection name="Notino.lv" dotColor="bg-[hsl(var(--success))]" products={notinoProductFeedItems} />
        )}
      </div>
    </div>
  );
}
