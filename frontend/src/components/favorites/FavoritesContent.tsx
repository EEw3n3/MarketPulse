import { useState } from "react";
import { Heart, TrendingDown, TrendingUp, Minus, Trash2, ExternalLink, Bell, BellOff } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";

interface FavoriteProduct {
  id: string;
  brand: string;
  name: string;
  currentPrice: number;
  previousPrice: number;
  lowestPrice: number;
  store: string;
  alertEnabled: boolean;
  addedDate: string;
}

const initialFavorites: FavoriteProduct[] = [
  { id: "1", brand: "Dior", name: "Sauvage EDP 100ml", currentPrice: 72.50, previousPrice: 88.90, lowestPrice: 68.00, store: "Notino", alertEnabled: true, addedDate: "2024-12-10" },
  { id: "2", brand: "Chanel", name: "Bleu de Chanel EDP 100ml", currentPrice: 98.00, previousPrice: 114.20, lowestPrice: 92.50, store: "Douglas", alertEnabled: true, addedDate: "2024-11-22" },
  { id: "3", brand: "Tom Ford", name: "Ombré Leather 50ml", currentPrice: 105.00, previousPrice: 118.60, lowestPrice: 99.00, store: "Sephora", alertEnabled: false, addedDate: "2025-01-05" },
  { id: "4", brand: "YSL", name: "Y Eau de Parfum 100ml", currentPrice: 68.90, previousPrice: 79.00, lowestPrice: 65.00, store: "Notino", alertEnabled: true, addedDate: "2025-01-18" },
  { id: "5", brand: "Versace", name: "Eros EDT 100ml", currentPrice: 52.40, previousPrice: 57.80, lowestPrice: 48.90, store: "Parfumdreams", alertEnabled: true, addedDate: "2024-12-28" },
  { id: "6", brand: "Armani", name: "Acqua di Giò Profondo 75ml", currentPrice: 84.30, previousPrice: 78.00, lowestPrice: 74.50, store: "Douglas", alertEnabled: false, addedDate: "2025-02-14" },
  { id: "7", brand: "Prada", name: "Luna Rossa Carbon 100ml", currentPrice: 76.90, previousPrice: 72.30, lowestPrice: 69.00, store: "Flaconi", alertEnabled: true, addedDate: "2025-01-30" },
  { id: "8", brand: "Hermès", name: "Terre d'Hermès EDP 75ml", currentPrice: 92.00, previousPrice: 87.50, lowestPrice: 82.00, store: "Sephora", alertEnabled: false, addedDate: "2025-02-20" },
];

function getChange(current: number, previous: number) {
  return ((current - previous) / previous) * 100;
}

export default function FavoritesContent() {
  const navigate = useNavigate();
  const [favorites, setFavorites] = useState(initialFavorites);
  const [sortBy, setSortBy] = useState("added");

  const sorted = [...favorites].sort((a, b) => {
    switch (sortBy) {
      case "price-asc": return a.currentPrice - b.currentPrice;
      case "price-desc": return b.currentPrice - a.currentPrice;
      case "change": return getChange(a.currentPrice, a.previousPrice) - getChange(b.currentPrice, b.previousPrice);
      default: return new Date(b.addedDate).getTime() - new Date(a.addedDate).getTime();
    }
  });

  const toggleAlert = (id: string) => {
    setFavorites(prev => prev.map(f => f.id === id ? { ...f, alertEnabled: !f.alertEnabled } : f));
  };

  const removeFavorite = (id: string) => {
    setFavorites(prev => prev.filter(f => f.id !== id));
  };

  const totalSavings = favorites.reduce((sum, f) => {
    const diff = f.previousPrice - f.currentPrice;
    return diff > 0 ? sum + diff : sum;
  }, 0);

  const dropsCount = favorites.filter(f => f.currentPrice < f.previousPrice).length;
  const alertsOn = favorites.filter(f => f.alertEnabled).length;

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-foreground">Favorites</h1>
            <p className="text-[13px] text-muted-foreground">
              Your personal watchlist — {favorites.length} products tracked
            </p>
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="h-8 w-[160px] border-border bg-surface-2 text-xs">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="added">Recently Added</SelectItem>
              <SelectItem value="price-asc">Price: Low → High</SelectItem>
              <SelectItem value="price-desc">Price: High → Low</SelectItem>
              <SelectItem value="change">Biggest Drop</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="p-6 space-y-5">
        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="relative overflow-hidden bg-[rgba(255,255,255,0.02)] backdrop-blur-[16px] border-border hover:-translate-y-1 hover:shadow-[0_8px_32px_rgba(0,0,0,0.5)] hover:border-[hsl(var(--success))]/30 transition-all duration-500 group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[hsl(var(--success))]/10 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 group-hover:bg-[hsl(var(--success))]/20 transition-colors duration-500 pointer-events-none" />
            <CardContent className="p-5 text-center relative z-10">
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground mb-1.5 font-medium group-hover:text-foreground transition-colors">Price Drops</p>
              <p className="font-display text-4xl font-bold text-[hsl(var(--success))] tabular-nums tracking-tight drop-shadow-[0_0_15px_rgba(var(--success),0.3)]">
                {dropsCount}
              </p>
              <p className="text-[11px] text-muted-foreground mt-1">of {favorites.length} products</p>
            </CardContent>
          </Card>

          <Card className="relative overflow-hidden bg-[rgba(255,255,255,0.02)] backdrop-blur-[16px] border-border hover:-translate-y-1 hover:shadow-[0_8px_32px_rgba(0,0,0,0.5)] hover:border-blue-500/30 transition-all duration-500 group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 group-hover:bg-blue-500/20 transition-colors duration-500 pointer-events-none" />
            <CardContent className="p-5 text-center relative z-10">
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground mb-1.5 font-medium group-hover:text-foreground transition-colors">Potential Savings</p>
              <p className="font-display text-4xl font-bold text-foreground tabular-nums tracking-tight">
                €{totalSavings.toFixed(0)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-1">vs. previous prices</p>
            </CardContent>
          </Card>

          <Card className="relative overflow-hidden bg-[rgba(255,255,255,0.02)] backdrop-blur-[16px] border-border hover:-translate-y-1 hover:shadow-[0_8px_32px_rgba(0,0,0,0.5)] hover:border-primary/40 transition-all duration-500 group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 group-hover:bg-primary/20 transition-colors duration-500 pointer-events-none" />
            <CardContent className="p-5 text-center relative z-10">
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground mb-1.5 font-medium group-hover:text-foreground transition-colors">Alerts Active</p>
              <p className="font-display text-4xl font-bold text-primary tabular-nums tracking-tight drop-shadow-[0_0_15px_rgba(124,58,237,0.3)]">
                {alertsOn}
              </p>
              <p className="text-[11px] text-muted-foreground mt-1">notifications on</p>
            </CardContent>
          </Card>
        </div>

        {/* Product List */}
        <div className="space-y-2">
          {sorted.map((product) => {
            const change = getChange(product.currentPrice, product.previousPrice);
            const isDown = change < 0;
            const isUp = change > 0;
            const atLowest = product.currentPrice <= product.lowestPrice;

            return (
              <Card
                key={product.id}
                className="relative overflow-hidden bg-surface border-border hover:border-primary/40 hover:-translate-y-1 hover:shadow-[0_12px_32px_rgba(0,0,0,0.5)] transition-all duration-300 cursor-pointer group"
                onClick={() => navigate(`/product/${product.id}`)}
              >
                <div className="absolute top-0 right-0 w-32 h-full bg-gradient-to-l from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                <CardContent className="p-4 flex items-center gap-4 relative z-10">
                  {/* Change Indicator */}
                  <div className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-transform duration-300 group-hover:scale-110",
                    isDown ? "bg-[hsl(var(--success))]/10 shadow-[0_0_15px_rgba(var(--success),0.2)]" : isUp ? "bg-destructive/10" : "bg-muted/10"
                  )}>
                    {isDown ? <TrendingDown size={18} className="text-[hsl(var(--success))]" /> :
                     isUp ? <TrendingUp size={18} className="text-destructive" /> :
                     <Minus size={18} className="text-muted-foreground" />}
                  </div>

                  {/* Product Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">{product.name}</p>
                      {atLowest && (
                        <Badge className="bg-[hsl(var(--success))]/15 text-[hsl(var(--success))] border-[hsl(var(--success))]/30 text-[10px] px-1.5 shrink-0 animate-pulse shadow-[0_0_8px_rgba(var(--success),0.4)]">
                          Lowest
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] uppercase tracking-widest text-muted-foreground mt-0.5">{product.brand} · <span className="text-foreground/70">{product.store}</span></p>
                  </div>

                  {/* Price */}
                  <div className="text-right shrink-0">
                    <p className="text-[15px] font-display font-bold text-foreground tabular-nums tracking-tight group-hover:scale-105 origin-right transition-transform">€{product.currentPrice.toFixed(2)}</p>
                    <div className="flex items-center justify-end gap-1.5 mt-0.5">
                      <span className="text-[11px] font-display text-muted-foreground line-through tabular-nums tracking-tight">
                        €{product.previousPrice.toFixed(2)}
                      </span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] px-1.5 font-display tabular-nums tracking-tight",
                          isDown ? "border-[hsl(var(--success))]/30 text-[hsl(var(--success))]" : isUp ? "border-destructive/30 text-destructive" : "border-border text-muted-foreground"
                        )}
                      >
                        {change > 0 ? "+" : ""}{change.toFixed(1)}%
                      </Badge>
                    </div>
                  </div>

                  {/* Alert Toggle */}
                  <div
                    className="shrink-0 flex items-center gap-2 pl-3 border-l border-border"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Switch
                      checked={product.alertEnabled}
                      onCheckedChange={() => toggleAlert(product.id)}
                      className="data-[state=checked]:bg-primary"
                    />
                    {product.alertEnabled
                      ? <Bell size={14} className="text-primary" />
                      : <BellOff size={14} className="text-muted-foreground" />
                    }
                  </div>

                  {/* Remove */}
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFavorite(product.id); }}
                    className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 size={14} />
                  </button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {favorites.length === 0 && (
          <div className="text-center py-24 relative overflow-hidden rounded-[var(--radius-card)] border border-dashed border-border/50 bg-[rgba(255,255,255,0.01)] backdrop-blur-sm">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary/5 rounded-full blur-[60px] pointer-events-none" />
            <div className="relative z-10 flex flex-col items-center">
              <div className="w-16 h-16 rounded-full bg-surface-2/80 border border-border flex items-center justify-center mb-4 shadow-glow">
                <Heart size={24} className="text-primary/70" />
              </div>
              <p className="text-lg font-display tracking-tight font-medium text-foreground">No favorites</p>
              <p className="text-[13px] text-muted-foreground mt-1.5 max-w-[250px] mx-auto">Track your most crucial products to receive instant dumping alerts.</p>
              <Button className="mt-6 h-9 px-6 text-[13px] shadow-glow hover:scale-105 transition-transform" onClick={() => navigate("/catalog")}>
                Browse Catalog
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
