import { useRef, useState } from "react";
import { RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

type Product = {
  id: number;
  brand: string;
  title: string;
  currentPrice: number;
  previousPrice: number;
  changePercent: number;
  changeDirection: "up" | "down";
  storeInitial: string;
  storeName?: string;
};

const mainProducts: Product[] = [
  { id: 1, brand: "DIOR", title: "Sauvage EDP, 100 ml", currentPrice: 125.0, previousPrice: 135.0, changePercent: 10, changeDirection: "down", storeInitial: "D" },
  { id: 2, brand: "HUGO BOSS", title: "Boss Bottled EDP, 200 ml", currentPrice: 89.99, previousPrice: 85.0, changePercent: 5, changeDirection: "up", storeInitial: "N" },
  { id: 3, brand: "VERSACE", title: "Eros EDT, 100 ml", currentPrice: 72.5, previousPrice: 82.0, changePercent: 12, changeDirection: "down", storeInitial: "D" },
  { id: 4, brand: "ARMANI", title: "Acqua di Giò Profondo, 75 ml", currentPrice: 98.0, previousPrice: 92.0, changePercent: 7, changeDirection: "up", storeInitial: "1" },
  { id: 5, brand: "PACO RABANNE", title: "1 Million Parfum, 100 ml", currentPrice: 79.99, previousPrice: 95.0, changePercent: 16, changeDirection: "down", storeInitial: "M" },
  { id: 6, brand: "LACOSTE", title: "L.12.12 Blanc EDT, 100 ml", currentPrice: 54.5, previousPrice: 52.0, changePercent: 5, changeDirection: "up", storeInitial: "N" },
  { id: 7, brand: "MONTBLANC", title: "Explorer EDP, 100 ml", currentPrice: 62.0, previousPrice: 70.0, changePercent: 11, changeDirection: "down", storeInitial: "2" },
  { id: 8, brand: "GIVENCHY", title: "Gentleman Society EDP, 100 ml", currentPrice: 105.0, previousPrice: 110.0, changePercent: 5, changeDirection: "down", storeInitial: "D" },
];

const douglasProducts: Product[] = [
  { id: 9, brand: "DIOR", title: "Miss Dior Blooming Bouquet, 100 ml", currentPrice: 99.0, previousPrice: 112.0, changePercent: 12, changeDirection: "down", storeInitial: "D" },
  { id: 10, brand: "CHANEL", title: "Bleu de Chanel EDP, 100 ml", currentPrice: 139.0, previousPrice: 135.0, changePercent: 3, changeDirection: "up", storeInitial: "D" },
  { id: 11, brand: "YSL", title: "Libre Intense EDP, 90 ml", currentPrice: 108.5, previousPrice: 120.0, changePercent: 10, changeDirection: "down", storeInitial: "D" },
  { id: 12, brand: "VALENTINO", title: "Donna Born In Roma, 100 ml", currentPrice: 95.0, previousPrice: 89.0, changePercent: 7, changeDirection: "up", storeInitial: "D" },
];

const notinoProducts: Product[] = [
  { id: 13, brand: "VERSACE", title: "Dylan Blue EDT, 100 ml", currentPrice: 58.0, previousPrice: 68.0, changePercent: 15, changeDirection: "down", storeInitial: "N" },
  { id: 14, brand: "ARMANI", title: "Stronger With You, 100 ml", currentPrice: 82.0, previousPrice: 78.0, changePercent: 5, changeDirection: "up", storeInitial: "N" },
  { id: 15, brand: "HUGO BOSS", title: "The Scent EDP, 100 ml", currentPrice: 67.99, previousPrice: 75.0, changePercent: 9, changeDirection: "down", storeInitial: "N" },
  { id: 16, brand: "PRADA", title: "Luna Rossa Carbon, 100 ml", currentPrice: 88.0, previousPrice: 84.0, changePercent: 5, changeDirection: "up", storeInitial: "N" },
];

function ProductCard({ product, small = false }: { product: Product; small?: boolean }) {
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
        <div className="text-muted-foreground text-xs opacity-40 select-none">📦</div>
        <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-white flex items-center justify-center">
          <span className="text-[9px] font-bold text-[hsl(240,50%,14%)]">{product.storeInitial}</span>
        </div>
        <div
          className={`absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[11px] font-bold ${
            product.changeDirection === "down"
              ? "bg-[hsl(var(--success))]/20 text-[hsl(var(--success))] animate-price-glow-green"
              : "bg-destructive/20 text-destructive animate-price-glow-red"
          }`}
        >
          {product.changeDirection === "down" ? "↓" : "↑"} {product.changeDirection === "down" ? "−" : "+"}
          {product.changePercent}%
        </div>
        <div className="absolute inset-0 bg-primary/50 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center">
          <span className="text-primary-foreground text-sm font-semibold">Learn More →</span>
        </div>
      </div>
      <div className={`${small ? "p-2" : "p-3"} flex flex-col gap-1`}>
        <span className="text-[11px] uppercase tracking-widest text-muted-foreground">{product.brand}</span>
        <span className={`${small ? "text-xs" : "text-[13px]"} font-semibold text-foreground line-clamp-2`}>{product.title}</span>
        <span className={`${priceSize} font-bold font-['Outfit',sans-serif] ${product.changeDirection === "down" ? "text-[hsl(var(--success))]" : "text-foreground"}`}>
          {product.currentPrice.toFixed(2)} €
        </span>
        <span className="text-[11px] text-muted-foreground line-through">{product.previousPrice.toFixed(2)} €</span>
      </div>
    </div>
  );
}

function ScrollableRow({ products, small = false }: { products: Product[]; small?: boolean }) {
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

function StoreSection({ name, dotColor, products }: { name: string; dotColor: string; products: Product[] }) {
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
  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between px-4 md:px-6 pt-6 pb-3">
        <h2 className="text-lg font-bold font-['Outfit',sans-serif] text-foreground">Latest Changes</h2>
        <div className="flex items-center gap-1 text-[13px] text-muted-foreground">
          <RefreshCw size={14} />
          Updated 3 minutes ago
        </div>
      </div>

      {/* Main carousel */}
      <div className="px-4 md:px-6">
        <ScrollableRow products={mainProducts} />
      </div>

      {/* Per-store sections */}
      <div className="px-4 md:px-6 flex flex-col gap-8 pb-6">
        <StoreSection name="Douglas.lv" dotColor="bg-blue-500" products={douglasProducts} />
        <StoreSection name="Notino.lv" dotColor="bg-[hsl(var(--success))]" products={notinoProducts} />
      </div>
    </div>
  );
}
