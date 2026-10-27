import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface FavoritesContextValue {
  ids: Set<number>;
  isFavorite: (productId: number) => boolean;
  toggleFavorite: (productId: number) => Promise<void>;
  loading: boolean;
}

const FavoritesContext = createContext<FavoritesContextValue | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const qc = useQueryClient();
  const [ids, setIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);

  // Hydrate when user becomes available
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setIds(new Set());
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .listFavorites()
      .then((favs) => {
        if (cancelled) return;
        setIds(new Set(favs.map((f) => f.product_id)));
      })
      .catch(() => {
        /* non-fatal — user can't toggle until this succeeds on retry */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, authLoading]);

  const isFavorite = useCallback((productId: number) => ids.has(productId), [ids]);

  const toggleFavorite = useCallback(
    async (productId: number) => {
      if (!user) return;
      const currentlyFav = ids.has(productId);

      // Optimistic
      setIds((prev) => {
        const next = new Set(prev);
        if (currentlyFav) next.delete(productId);
        else next.add(productId);
        return next;
      });

      try {
        if (currentlyFav) {
          await api.removeFavorite(productId);
        } else {
          await api.addFavorite(productId);
        }
        qc.invalidateQueries({ queryKey: ["favorites"] });
      } catch (err) {
        // Revert
        setIds((prev) => {
          const next = new Set(prev);
          if (currentlyFav) next.add(productId);
          else next.delete(productId);
          return next;
        });
        console.error("Failed to toggle favorite:", err);
      }
    },
    [ids, user, qc]
  );

  return (
    <FavoritesContext.Provider value={{ ids, isFavorite, toggleFavorite, loading }}>
      {children}
    </FavoritesContext.Provider>
  );
}

export function useFavorites(): FavoritesContextValue {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error("useFavorites must be used inside FavoritesProvider");
  return ctx;
}
