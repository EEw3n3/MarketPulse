import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CardOffer, CatalogCard, FacetValue } from "@/lib/api";
import { FILTER_PARAMS, shopCount, sizeOptions, soldOut, stockParam, withoutFilters } from "@/lib/catalog";
import { exportUrl } from "@/lib/download";
import { I18nProvider } from "@/i18n";
import { FavoritesProvider } from "@/contexts/FavoritesContext";
import { AuthProvider } from "@/contexts/AuthContext";
import Tile from "@/components/mp/Tile";

function offer(store: string, in_stock = true, price = 50, product_id = 1): CardOffer {
  return {
    product_id,
    store,
    store_name: store,
    title: "Dior Sauvage EDT 100ml",
    price,
    old_price: null,
    promo_price: null,
    promo_code: null,
    url: "https://example.test/p",
    in_stock,
    checked_at: null,
    change_30d: null,
  } as CardOffer;
}

function card(over: Partial<CatalogCard> = {}): CatalogCard {
  const offers = over.offers ?? [offer("douglas")];
  return {
    key: "g1:100ml",
    product_id: 1,
    brand: "Dior",
    name: "Sauvage",
    concentration: "EDT",
    volume: "100ml",
    image_url: null,
    min_price: 50,
    max_price: 50,
    cheapest_store: "douglas",
    shops: new Set(offers.map((o) => o.store)).size,
    change_30d: null,
    has_promo: false,
    offers,
    ...over,
  };
}

function renderTile(c: CatalogCard) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter>
      <I18nProvider>
        <AuthProvider>
          <FavoritesProvider>
            <Tile card={c} />
          </FavoritesProvider>
        </AuthProvider>
      </I18nProvider>
    </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("1. shop count on a card", () => {
  it("uses the server's total when the shop filter left one offer", () => {
    expect(shopCount(card({ offers: [offer("douglas")], shops: 1, shops_total: 3 }))).toBe(3);
  });
  it("falls back to the in-stock shops among the offers", () => {
    expect(shopCount(card({ offers: [offer("douglas"), offer("notino"), offer("makeup", false)], shops: 3 }))).toBe(2);
  });
  it("counts a shop that lists the bottle twice once", () => {
    expect(shopCount(card({ offers: [offer("douglas"), offer("douglas", true, 55, 2)], shops: 1 }))).toBe(1);
  });
  it("falls back to card.shops when nothing is in stock", () => {
    expect(shopCount(card({ offers: [offer("douglas", false), offer("notino", false)], shops: 2 }))).toBe(2);
  });
  it("the tile prints the total, not the filtered count", () => {
    renderTile(card({ offers: [offer("douglas")], shops: 1, shops_total: 3 }));
    expect(screen.getByText(/3 shops/)).toBeInTheDocument();
    expect(screen.queryByText(/1 shop\b/)).not.toBeInTheDocument();
  });
});

describe("2. out of stock is marked on the card", () => {
  it("soldOut is true only when no shown offer is in stock", () => {
    expect(soldOut(card({ offers: [offer("douglas", false)] }))).toBe(true);
    expect(soldOut(card({ offers: [offer("douglas", false), offer("notino")] }))).toBe(false);
    expect(soldOut(card({ offers: [] }))).toBe(false);
  });
  it("a sold-out tile shows the badge and the is-out class", () => {
    const { container } = renderTile(card({ offers: [offer("douglas", false)] }));
    expect(container.querySelector(".t-out")).toHaveTextContent("Out of stock");
    expect(container.querySelector(".tile")).toHaveClass("is-out");
  });
  it("an in-stock tile has no badge", () => {
    const { container } = renderTile(card());
    expect(container.querySelector(".t-out")).toBeNull();
    expect(container.querySelector(".tile")).not.toHaveClass("is-out");
  });
});

describe("3. clearing the filters", () => {
  it("removes every filter and the page, keeps the view and the sort", () => {
    const sp = new URLSearchParams(
      "q=dior&shop=douglas&shop=notino&type=EDP&vol=100ml&brand=Dior&pmin=10&pmax=90&stock=0&promo=1&multi=1&dropped=1&page=4&view=table&sort=low&tsort=price&tdir=desc",
    );
    const next = withoutFilters(sp);
    expect(next.toString()).toBe("view=table&sort=low&tsort=price&tdir=desc");
    FILTER_PARAMS.forEach((k) => expect(next.has(k)).toBe(false));
  });
  it("does not change the parameters it was given", () => {
    const sp = new URLSearchParams("q=dior&shop=douglas");
    withoutFilters(sp);
    expect(sp.toString()).toBe("q=dior&shop=douglas");
  });
  it("with no filters the result is empty", () => {
    expect(withoutFilters(new URLSearchParams("")).toString()).toBe("");
  });
});

describe("4. sizes for the picked brand", () => {
  const all: FacetValue[] = [
    { value: "30ml", label: "30 ml", count: 400 },
    { value: "50ml", label: "50 ml", count: 900 },
    { value: "75ml", label: "75 ml", count: 12 },
    { value: "100ml", label: "100 ml", count: 1500 },
  ];
  const dior: FacetValue[] = [
    { value: "60ml", label: "60 ml", count: 7 },
    { value: "100ml", label: "100 ml", count: 21 },
  ];
  it("no brand: the common sizes with catalogue-wide counts", () => {
    expect(sizeOptions({ all, picked: [], showAll: false }).map((v) => [v.value, v.count])).toEqual([
      ["30ml", 400],
      ["50ml", 900],
      ["100ml", 1500],
    ]);
  });
  it("no brand, All: every size", () => {
    expect(sizeOptions({ all, picked: [], showAll: true }).map((v) => v.value)).toEqual(["30ml", "50ml", "75ml", "100ml"]);
  });
  it("brand picked: only that brand's sizes with its own counts, rare ones too", () => {
    expect(sizeOptions({ all, forBrands: dior, picked: [], showAll: false }).map((v) => [v.value, v.count])).toEqual([
      ["60ml", 7],
      ["100ml", 21],
    ]);
  });
  it("a ticked size the brand does not have stays, with a zero count", () => {
    const got = sizeOptions({ all, forBrands: dior, picked: ["50ml"], showAll: false });
    expect(got.map((v) => [v.value, v.label, v.count])).toEqual([
      ["50ml", "50 ml", 0],
      ["60ml", "60 ml", 7],
      ["100ml", "100 ml", 21],
    ]);
  });
  it("a ticked rare size stays in the general list", () => {
    expect(sizeOptions({ all, picked: ["75ml"], showAll: false }).map((v) => v.value)).toEqual(["30ml", "50ml", "75ml", "100ml"]);
  });
});

describe("5. out-of-stock filter", () => {
  it("reads the stock parameter", () => {
    expect(stockParam("1")).toBe(true);
    expect(stockParam("0")).toBe(false);
    expect(stockParam(null)).toBeUndefined();
    expect(stockParam("x")).toBeUndefined();
  });
  it("in_stock=false reaches the export URL, other false flags do not", () => {
    const url = exportUrl("/exports/catalog", { format: "xlsx", in_stock: false, promo: false, multi_shop: undefined });
    expect(url).toBe("/exports/catalog?format=xlsx&in_stock=false");
  });
  it("in_stock=true and undefined behave as before", () => {
    expect(exportUrl("/x", { in_stock: true })).toBe("/x?in_stock=true");
    expect(exportUrl("/x", { in_stock: undefined, a: 1 })).toBe("/x?a=1");
  });
});
