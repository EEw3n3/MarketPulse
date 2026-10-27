import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import type { CatalogCard } from "@/lib/api";
import { eur, pct } from "@/lib/format";
import { fieldStyle, shopKey, shopOf } from "@/lib/shops";
import { useT } from "@/i18n";
import Heart from "./Heart";
import Img from "./Img";
import { spec } from "./SearchBox";

/** One perfume in one size, painted in the colour of its cheapest shop. */
export default function Tile({
  card,
  picking = false,
  picked = false,
  onPick,
  style,
  className = "",
}: {
  card: CatalogCard;
  picking?: boolean;
  picked?: boolean;
  onPick?: () => void;
  style?: React.CSSProperties;
  className?: string;
}) {
  const t = useT();
  const shop = shopOf(card.cheapest_store);
  const c = card.change_30d;
  const steady = c == null || Math.abs(c) < 0.5;
  const title = `${card.brand} ${card.name}`;
  // A shop can list the same bottle more than once; count shops, not listings.
  const live = new Set(card.offers.filter((o) => o.in_stock).map((o) => shopKey(o.store))).size || card.shops;
  return (
    <div className={`tile ${picked ? "sel" : ""} ${className}`} style={{ ...fieldStyle(card.cheapest_store), ...style }}>
      <Link
        to={`/product/${card.product_id}`}
        className="t-cover"
        aria-label={`${title}, ${spec(card)}, ${eur(card.min_price)} ${t.common.at(shop.label)}`}
        onClick={(e) => {
          if (picking && onPick) {
            e.preventDefault();
            onPick();
          }
        }}
      />
      <div className="t-top">
        <span className="where">{shop.label}</span>
        <span className="t-chg num">
          {steady ? (
            t.common.steady
          ) : (
            <>
              {c! < 0 ? "↓ " : "↑ "}
              {pct(Math.abs(c!)).replace("+", "")}
              <span className="long"> {t.common.inDays(30)}</span>
            </>
          )}
        </span>
      </div>
      <div className="t-pic">
        <Img src={card.image_url} brand={card.brand} />
      </div>
      <div>
        <div className="t-name">
          {card.brand}{" "}
          <span>
            {card.name}
            {spec(card) ? ` · ${spec(card)}` : ""}
          </span>
        </div>
        <div className="t-foot">
          <span className="t-price num">{eur(card.min_price)}</span>
          <span className="t-meta num">
            {t.common.shops(live)}
            {card.max_price > card.min_price + 0.5 && (
              <>
                <br />
                {t.common.upTo(eur(card.max_price))}
              </>
            )}
          </span>
        </div>
      </div>
      {picking ? (
        <button
          className="pick"
          type="button"
          aria-pressed={picked}
          aria-label={title}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onPick?.();
          }}
        >
          {picked && <Check />}
        </button>
      ) : null}
      <Heart ids={[card.product_id, ...card.offers.map((o) => o.product_id).filter((id) => id !== card.product_id)]} label={title} />
    </div>
  );
}
