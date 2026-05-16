import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Heart,
  ArrowDown,
  ArrowUp,
  Bell,
  BellOff,
  Trash2,
  RefreshCw,
  AlertCircle,
  Package,
  AlertTriangle,
} from "lucide-react";
import { api, FavoriteItem } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

type SortKey = "added" | "price_asc" | "price_desc" | "change";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "added", label: "Recently added" },
  { value: "price_asc", label: "Price · low to high" },
  { value: "price_desc", label: "Price · high to low" },
  { value: "change", label: "Biggest drop" },
];

function storeTag(name: string): string {
  return name.replace(/\.lv$/i, "").replace(/\s+latvia$/i, "").trim().slice(0, 2).toUpperCase();
}

function ChangePill({ direction, percent }: { direction: "up" | "down" | "none"; percent: number }) {
  if (direction === "none") {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[10px] font-medium text-muted-foreground px-1.5 py-0.5 rounded bg-surface-2/70 border border-border">
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
      className={`inline-flex items-center gap-1 font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded ${tone} ${border} ${bg} border`}
    >
      <Icon size={9} strokeWidth={2.75} />
      {isDown ? "−" : "+"}
      {percent.toFixed(1)}%
    </span>
  );
}

export default function FavoritesContent() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState<FavoriteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("added");

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listFavorites();
      setItems(data);
    } catch (err) {
      console.error("Failed to load favorites:", err);
      setError("Could not load your watchlist.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const sorted = [...items].sort((a, b) => {
    switch (sort) {
      case "price_asc":
        return a.current_price - b.current_price;
      case "price_desc":
        return b.current_price - a.current_price;
      case "change": {
        const va = a.change_direction === "down" ? -a.change_percent : a.change_percent;
        const vb = b.change_direction === "down" ? -b.change_percent : b.change_percent;
        return va - vb;
      }
      default:
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
  });

  const droppedCount = items.filter((f) => f.change_direction === "down").length;
  const alertsOn = items.filter((f) => f.alert_enabled).length;
  const potentialSavings = items.reduce((sum, f) => {
    if (f.previous_price && f.previous_price > f.current_price) {
      return sum + (f.previous_price - f.current_price);
    }
    return sum;
  }, 0);

  const handleToggleAlert = async (fav: FavoriteItem) => {
    setItems((prev) =>
      prev.map((f) => (f.product_id === fav.product_id ? { ...f, alert_enabled: !f.alert_enabled } : f))
    );
    try {
      await api.updateFavorite(fav.product_id, !fav.alert_enabled);
    } catch {
      // revert on failure
      setItems((prev) =>
        prev.map((f) => (f.product_id === fav.product_id ? { ...f, alert_enabled: fav.alert_enabled } : f))
      );
    }
  };

  const handleRemove = async (productId: number) => {
    const prev = items;
    setItems((p) => p.filter((f) => f.product_id !== productId));
    try {
      await api.removeFavorite(productId);
    } catch {
      setItems(prev);
    }
  };

  const hasAlertsOn = items.some((f) => f.alert_enabled);
  const channelsConfigured = (user?.preferences?.notification_channels?.length ?? 0) > 0;
  const showChannelWarning = !loading && hasAlertsOn && !channelsConfigured;

  return (
    <div className="flex-1 overflow-y-auto">
      {/* ── No-channel warning ─────────────────────────────────── */}
      {showChannelWarning && (
        <div className="mx-5 lg:mx-7 mt-4 flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/[0.07] px-4 py-3">
          <AlertTriangle size={14} className="text-amber-500 shrink-0 mt-0.5" strokeWidth={2} />
          <p className="text-[12.5px] text-amber-200/90 leading-relaxed">
            Alerts are on, but no delivery channel is configured.{" "}
            <button
              onClick={() => navigate("/settings")}
              className="underline underline-offset-2 hover:text-amber-100 transition-colors"
            >
              Set up notifications in Settings
            </button>
            .
          </p>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-5 lg:px-7 pt-7 pb-5 border-b border-border">
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
              · Watchlist
            </p>
            <div className="flex items-baseline gap-3">
              <h1 className="font-['Inter'] font-semibold text-foreground text-[22px] tracking-[-0.01em]">
                Favorites
              </h1>
              <span className="font-mono tabular-nums text-[12px] text-muted-foreground">
                {items.length} {items.length === 1 ? "product" : "products"}
              </span>
            </div>
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Sort
            </span>
            <div className="flex items-center gap-0.5 p-0.5 rounded-md border border-border bg-surface">
              {SORT_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  onClick={() => setSort(o.value)}
                  className={cn(
                    "px-2.5 py-1 rounded font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] transition-colors whitespace-nowrap",
                    sort === o.value
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Status strip ───────────────────────────────────────── */}
      {items.length > 0 && (
        <div className="px-5 lg:px-7 py-3 border-b border-border flex items-center gap-6 text-[12px] flex-wrap">
          <span className="flex items-center gap-1.5 text-[hsl(var(--success))]">
            <ArrowDown size={11} strokeWidth={2.5} />
            <span className="font-mono tabular-nums">{droppedCount}</span>
            <span className="text-muted-foreground">dropped</span>
          </span>
          <span className="w-px h-3 bg-border" />
          <span className="flex items-center gap-1.5">
            <span className="font-mono tabular-nums text-foreground">€{potentialSavings.toFixed(0)}</span>
            <span className="text-muted-foreground">potential savings</span>
          </span>
          <span className="w-px h-3 bg-border" />
          <span className="flex items-center gap-1.5">
            <Bell size={11} className="text-primary" strokeWidth={2} />
            <span className="font-mono tabular-nums text-foreground">{alertsOn}</span>
            <span className="text-muted-foreground">alerts active</span>
          </span>
        </div>
      )}

      {/* ── Body ───────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex flex-col items-center justify-center h-[400px] gap-3">
          <RefreshCw className="animate-spin text-muted-foreground" size={18} />
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            Loading watchlist
          </p>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center h-[400px] gap-3 px-6 text-center">
          <AlertCircle className="text-destructive" size={22} />
          <p className="text-foreground text-[13px]">{error}</p>
          <button
            onClick={load}
            className="text-[12px] text-muted-foreground hover:text-foreground underline underline-offset-2"
          >
            Try again
          </button>
        </div>
      ) : items.length === 0 ? (
        <EmptyState onBrowse={() => navigate("/catalog")} />
      ) : (
        <div className="divide-y divide-border">
          {sorted.map((f) => (
            <FavoriteRow
              key={f.id}
              fav={f}
              onOpen={() => navigate(`/product/${f.product_id}`)}
              onToggleAlert={() => handleToggleAlert(f)}
              onRemove={() => handleRemove(f.product_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────

function FavoriteRow({
  fav,
  onOpen,
  onToggleAlert,
  onRemove,
}: {
  fav: FavoriteItem;
  onOpen: () => void;
  onToggleAlert: () => void;
  onRemove: () => void;
}) {
  const hasPrevious = fav.previous_price !== null && fav.previous_price !== fav.current_price;
  const savingsFromEntry =
    fav.price_when_added && fav.price_when_added > fav.current_price
      ? fav.price_when_added - fav.current_price
      : 0;

  return (
    <div
      onClick={onOpen}
      className="group flex items-center gap-4 px-5 lg:px-7 py-4 hover:bg-surface/40 transition-colors cursor-pointer"
    >
      {/* Thumbnail */}
      <div className="w-12 h-12 rounded-md bg-surface-2 border border-border shrink-0 flex items-center justify-center overflow-hidden">
        {fav.image_url ? (
          <img
            src={fav.image_url}
            alt={fav.title}
            className="w-full h-full object-contain p-1"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <Package size={16} className="text-muted-foreground/40" strokeWidth={1.25} />
        )}
      </div>

      {/* Brand + Title */}
      <div className="flex-1 min-w-0">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground font-medium truncate">
          {fav.brand ?? "—"}
        </p>
        <p className="text-[13px] text-foreground truncate">
          {fav.title}
          {fav.volume && fav.volume !== "N/A" && (
            <span className="text-muted-foreground ml-2 font-mono tabular-nums text-[11.5px]">
              {fav.volume}
            </span>
          )}
        </p>
        <p className="font-mono text-[10px] text-muted-foreground/70 mt-0.5">
          Added {new Date(fav.created_at).toLocaleString("en-GB", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>

      {/* Store tag */}
      <div className="hidden md:flex items-center gap-2 shrink-0 w-[130px]">
        <span className="w-7 h-5 rounded-sm bg-surface-2 border border-border font-mono text-[9px] font-medium text-muted-foreground flex items-center justify-center">
          {storeTag(fav.store_name)}
        </span>
        <span className="text-[12px] text-muted-foreground truncate">{fav.store_name}</span>
      </div>

      {/* Price block */}
      <div className="flex flex-col items-end shrink-0 w-[130px]">
        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              "font-mono font-semibold tabular-nums text-[15px]",
              fav.change_direction === "down" ? "text-[hsl(var(--success))]" : "text-foreground"
            )}
          >
            {fav.current_price.toFixed(2)} €
          </span>
          {hasPrevious && (
            <span className="font-mono tabular-nums text-[11px] text-muted-foreground line-through">
              {fav.previous_price!.toFixed(2)}
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-1.5">
          <ChangePill direction={fav.change_direction} percent={fav.change_percent} />
          {savingsFromEntry > 0.01 && (
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              −{savingsFromEntry.toFixed(2)}€ since added
            </span>
          )}
        </div>
      </div>

      {/* Alert toggle */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggleAlert();
        }}
        className={cn(
          "w-8 h-8 rounded-md flex items-center justify-center transition-colors shrink-0",
          fav.alert_enabled
            ? "text-primary hover:bg-primary/10"
            : "text-muted-foreground/60 hover:text-foreground hover:bg-surface"
        )}
        aria-label={fav.alert_enabled ? "Disable alert" : "Enable alert"}
        title={fav.alert_enabled ? "Alert on — click to mute" : "Alert off — click to enable"}
      >
        {fav.alert_enabled ? <Bell size={14} strokeWidth={1.75} /> : <BellOff size={14} strokeWidth={1.75} />}
      </button>

      {/* Remove */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground/60 hover:text-destructive hover:bg-destructive/[0.08] transition-colors shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100"
        aria-label="Remove from watchlist"
      >
        <Trash2 size={13} strokeWidth={1.75} />
      </button>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────

function EmptyState({ onBrowse }: { onBrowse: () => void }) {
  return (
    <div className="px-5 lg:px-7 py-20">
      <div className="max-w-md mx-auto flex flex-col items-center text-center gap-4">
        <div className="w-12 h-12 rounded-md bg-surface-2 border border-border flex items-center justify-center">
          <Heart size={18} className="text-muted-foreground/60" strokeWidth={1.5} />
        </div>
        <div className="flex flex-col gap-1.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            No favorites yet
          </p>
          <h2 className="font-['Inter'] font-semibold text-foreground text-[18px] tracking-[-0.01em]">
            Pin products you care about.
          </h2>
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            MarketPulse will watch the shelves and alert you when prices move.
          </p>
        </div>
        <button
          onClick={onBrowse}
          className="h-9 px-4 rounded-md bg-foreground text-background text-[12.5px] font-medium hover:bg-foreground/90 transition-colors"
        >
          Browse catalog
        </button>
      </div>
    </div>
  );
}
