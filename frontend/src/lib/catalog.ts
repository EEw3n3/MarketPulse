// Small pure rules of the catalogue page, kept out of the components so they
// can be tested on their own.
import type { CatalogCard, FacetValue } from "@/lib/api";
import { shopKey } from "@/lib/shops";

/** How many shops sell the bottle. The shop and stock filters trim a card's
 *  offers, so the server sends the count over every listing (`shops_total`);
 *  the offers are only a fallback. A shop that lists a bottle twice counts once. */
export function shopCount(card: Pick<CatalogCard, "offers" | "shops"> & { shops_total?: number | null }): number {
  if (card.shops_total && card.shops_total > 0) return card.shops_total;
  return new Set(card.offers.filter((o) => o.in_stock).map((o) => shopKey(o.store))).size || card.shops;
}

/** True when none of the listings the card shows is in stock. */
export function soldOut(card: Pick<CatalogCard, "offers">): boolean {
  return card.offers.length > 0 && !card.offers.some((o) => o.in_stock);
}

/** The "stock" URL parameter: "1" = in stock only, "0" = out of stock only. */
export function stockParam(v: string | null): boolean | undefined {
  return v === "1" ? true : v === "0" ? false : undefined;
}

/** Sizes for the Size block. Without a brand: the catalogue-wide list (common
 *  sizes, or all of them). With brands picked: exactly the sizes those brands
 *  come in, with their own counts. A size the user already ticked always stays
 *  visible so it can be unticked. */
export function sizeOptions(opts: {
  all: FacetValue[];
  forBrands?: FacetValue[] | null;
  picked: string[];
  showAll: boolean;
  commonFrom?: number;
}): FacetValue[] {
  const { all, forBrands, picked, showAll, commonFrom = 30 } = opts;
  const base = forBrands ? forBrands.filter((v) => v.count > 0) : showAll ? all : all.filter((v) => v.count >= commonFrom);
  const have = new Set(base.map((v) => v.value));
  const extra = picked
    .filter((p) => !have.has(p))
    .map((p) => {
      const known = all.find((v) => v.value === p);
      return { value: p, label: known?.label ?? p, count: forBrands ? 0 : known?.count ?? 0 };
    });
  const ml = (v: FacetValue) => parseFloat(v.value) || 0;
  return [...base, ...extra].sort((a, b) => ml(a) - ml(b) || a.value.localeCompare(b.value));
}

/** URL parameters that are filters. Clearing filters removes these and keeps
 *  the view and the sort order. */
export const FILTER_PARAMS = ["q", "shop", "type", "vol", "brand", "pmin", "pmax", "stock", "promo", "multi", "dropped", "page"];

export function withoutFilters(sp: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(sp);
  FILTER_PARAMS.forEach((k) => next.delete(k));
  return next;
}
