import { useNavigate } from "react-router-dom";
import { Heart as HeartIcon } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useFavorites } from "@/contexts/FavoritesContext";
import { useT } from "@/i18n";

/** Heart toggle for a bottle. `ids` are every listing of the bottle; it shows
 *  as saved when any of them is a favorite, and adds the cheapest one. */
export default function Heart({ ids, label, className = "heart" }: { ids: number[]; label: string; className?: string }) {
  const t = useT();
  const { user } = useAuth();
  const nav = useNavigate();
  const { isFavorite, toggleFavorite } = useFavorites();
  const saved = ids.filter((id) => isFavorite(id));
  const on = saved.length > 0;
  return (
    <button
      className={className}
      type="button"
      aria-pressed={on}
      aria-label={on ? t.common.removeFav(label) : t.common.addFav(label)}
      onClick={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!user) {
          nav("/register");
          return;
        }
        if (on) {
          for (const id of saved) await toggleFavorite(id);
          toast(t.common.favRemoved);
        } else {
          await toggleFavorite(ids[0]);
          toast(t.common.favAdded);
        }
      }}
    >
      <HeartIcon />
    </button>
  );
}
