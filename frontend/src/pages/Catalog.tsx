import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowUpRight, LayoutGrid, ListChecks, Rows3, SlidersHorizontal, X } from "lucide-react";
import { api, type CardSort, type CatalogQuery, type ListingSort } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { usePageContext } from "@/contexts/ChatContext";
import { useT } from "@/i18n";
import { exportUrl } from "@/lib/download";
import { day, eur, int, pct } from "@/lib/format";
import { hasPro } from "@/lib/plan";
import { LIVE_SHOPS, SHOPS, shopOf } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";
import ExportMenu from "@/components/mp/ExportMenu";
import Pager from "@/components/mp/Pager";
import SearchBox from "@/components/mp/SearchBox";
import ShopPill from "@/components/mp/ShopPill";
import Tile from "@/components/mp/Tile";
import useFlip from "@/components/mp/useFlip";
import usePeek from "@/components/mp/usePeek";

const CARDS_PER_PAGE = 24;
const ROWS_PER_PAGE = 50;
const CARD_SORTS: CardSort[] = ["popular", "shops", "drop", "low", "high", "gap", "brand", "new"];

function num(v: string | null): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function Catalog() {
  const t = useT();
  const nav = useNavigate();
  const { user } = useAuth();
  const pro = hasPro(user);
  const [sp, setSp] = useSearchParams();
  const peek = usePeek<HTMLTableSectionElement>();

  // Every filter lives in the URL, so a filtered catalogue can be bookmarked.
  const search = sp.get("q") ?? "";
  const stores = sp.getAll("shop");
  const types = sp.getAll("type");
  const volumes = sp.getAll("vol");
  const brands = sp.getAll("brand");
  const priceMin = num(sp.get("pmin"));
  const priceMax = num(sp.get("pmax"));
  const inStock = sp.get("stock") === "1";
  const promo = sp.get("promo") === "1";
  const multi = sp.get("multi") === "1";
  const dropped = sp.get("dropped") === "1";
  const view = sp.get("view") === "table" ? "table" : "cards";
  const sort = (CARD_SORTS.includes(sp.get("sort") as CardSort) ? sp.get("sort") : "popular") as CardSort;
  const tsort = (["popular", "brand", "name", "price", "change", "shop"].includes(sp.get("tsort") ?? "") ? sp.get("tsort") : "popular") as ListingSort;
  const tdir = sp.get("tdir") === "desc" ? "desc" : "asc";
  const page = Math.max(1, Number(sp.get("page")) || 1);

  const [more, setMore] = useState(() => !!(volumes.length || brands.length || priceMin != null || priceMax != null || inStock || promo || multi || dropped));
  const [brandQ, setBrandQ] = useState("");
  const [minDraft, setMinDraft] = useState(priceMin?.toString() ?? "");
  const [maxDraft, setMaxDraft] = useState(priceMax?.toString() ?? "");
  const [picking, setPicking] = useState(false);
  const [pickedKeys, setPickedKeys] = useState<Set<string>>(new Set());
  const [pickedIds, setPickedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setMinDraft(priceMin?.toString() ?? "");
    setMaxDraft(priceMax?.toString() ?? "");
  }, [priceMin, priceMax]);

  function update(fn: (p: URLSearchParams) => void, keepPage = false) {
    const next = new URLSearchParams(sp);
    fn(next);
    if (!keepPage) next.delete("page");
    setSp(next, { replace: true });
  }
  const setOne = (k: string, v: string | null) => update((p) => (v == null || v === "" ? p.delete(k) : p.set(k, v)));
  const toggleIn = (k: string, v: string) =>
    update((p) => {
      const cur = p.getAll(k);
      p.delete(k);
      (cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]).forEach((x) => p.append(k, x));
    });
  const setPage = (n: number) => {
    update((p) => (n > 1 ? p.set("page", String(n)) : p.delete("page")), true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const query: CatalogQuery = {
    search: search || undefined,
    stores: stores.length ? stores : undefined,
    types: types.length ? types : undefined,
    volumes: volumes.length ? volumes : undefined,
    brands: brands.length ? brands : undefined,
    price_min: priceMin,
    price_max: priceMax,
    in_stock: inStock || undefined,
    promo: promo || undefined,
    multi_shop: multi || undefined,
    dropped: dropped || undefined,
  };

  const facets = useQuery({ queryKey: ["filters"], queryFn: api.getFilters, staleTime: 10 * 60_000 });
  const cards = useQuery({
    queryKey: ["cards", query, sort, page],
    queryFn: () => api.getCards({ ...query, sort, skip: (page - 1) * CARDS_PER_PAGE, limit: CARDS_PER_PAGE }),
    enabled: view === "cards",
    placeholderData: keepPreviousData,
  });
  const rows = useQuery({
    queryKey: ["listings", query, tsort, tdir, page],
    queryFn: () => api.getListings({ ...query, sort: tsort, direction: tdir, skip: (page - 1) * ROWS_PER_PAGE, limit: ROWS_PER_PAGE }),
    enabled: view === "table",
    placeholderData: keepPreviousData,
  });
  const flip = useFlip<HTMLDivElement>(cards.data);

  const f = facets.data;
  const typeOpts = (f?.concentrations ?? []).map((c) => ({ ...c, label: c.value === "other" ? t.catalog.other : c.label }));
  const commonVols = useMemo(() => (f?.volumes ?? []).filter((v) => v.count >= 30), [f]);
  const quickVols = useMemo(() => commonVols.slice().sort((a, b) => b.count - a.count).slice(0, 4).sort((a, b) => parseFloat(a.value) - parseFloat(b.value)), [commonVols]);
  const [allVols, setAllVols] = useState(false);
  const volOpts = allVols ? f?.volumes ?? [] : commonVols;
  const brandOpts = useMemo(() => {
    const all = f?.brands ?? [];
    const q = brandQ.trim().toLowerCase();
    const hits = q ? all.filter((b) => b.label.toLowerCase().includes(q)) : all.slice().sort((a, b) => b.count - a.count);
    return hits.slice(0, 40);
  }, [f, brandQ]);

  const totalCards = cards.data?.total ?? 0;
  const totalListings = view === "cards" ? cards.data?.listings ?? 0 : rows.data?.total ?? 0;
  const pagesTotal = view === "cards" ? Math.ceil(totalCards / CARDS_PER_PAGE) : Math.ceil((rows.data?.total ?? 0) / ROWS_PER_PAGE);

  const ctxBits = [search && `search "${search}"`, stores.length && `shops ${stores.join(", ")}`, types.length && types.join("/"), volumes.length && volumes.join(", "), brands.length && `brands ${brands.join(", ")}`]
    .filter(Boolean)
    .join("; ");
  usePageContext(`Catalogue${ctxBits ? ` filtered by ${ctxBits}` : ""}`);

  const active: { label: string; clear: () => void }[] = [
    ...(search ? [{ label: `“${search}”`, clear: () => setOne("q", null) }] : []),
    ...stores.map((s) => ({ label: shopOf(s).label, clear: () => toggleIn("shop", s) })),
    ...types.map((s) => ({ label: s === "other" ? t.catalog.other : s, clear: () => toggleIn("type", s) })),
    ...volumes.map((s) => ({ label: s, clear: () => toggleIn("vol", s) })),
    ...brands.map((s) => ({ label: s, clear: () => toggleIn("brand", s) })),
    ...(priceMin != null || priceMax != null
      ? [
          {
            label: priceMin != null && priceMax != null ? t.catalog.between(eur(priceMin, 0), eur(priceMax, 0)) : priceMin != null ? t.catalog.over(eur(priceMin, 0)) : t.catalog.under(eur(priceMax, 0)),
            clear: () => update((p) => (p.delete("pmin"), p.delete("pmax"))),
          },
        ]
      : []),
    ...(inStock ? [{ label: t.catalog.inStock, clear: () => setOne("stock", null) }] : []),
    ...(promo ? [{ label: t.catalog.promo, clear: () => setOne("promo", null) }] : []),
    ...(multi ? [{ label: t.catalog.multi, clear: () => setOne("multi", null) }] : []),
    ...(dropped ? [{ label: t.catalog.dropped, clear: () => setOne("dropped", null) }] : []),
  ];
  const extraCount = volumes.length + brands.length + (priceMin != null || priceMax != null ? 1 : 0) + [inStock, promo, multi, dropped].filter(Boolean).length;

  const exportFilters = {
    search: query.search,
    stores: query.stores,
    types: query.types,
    volumes: query.volumes,
    brands: query.brands,
    price_min: query.price_min,
    price_max: query.price_max,
    in_stock: query.in_stock,
    promo: query.promo,
    multi_shop: query.multi_shop,
    dropped: query.dropped,
  };
  const pickedN = view === "cards" ? pickedKeys.size : pickedIds.size;
  const exportAll = (fmt: string) =>
    exportUrl("/exports/catalog", { format: fmt, view: view === "cards" ? "cards" : "listings", ...exportFilters, sort: view === "cards" ? sort : tsort, limit: 5000 });
  const exportPicked = (fmt: string) =>
    exportUrl("/exports/catalog", view === "cards" ? { format: fmt, view: "cards", keys: [...pickedKeys] } : { format: fmt, view: "listings", ids: [...pickedIds], limit: 5000 });

  function applyPrice(min: string, max: string) {
    update((p) => {
      if (min.trim()) p.set("pmin", String(Math.max(0, Number(min))));
      else p.delete("pmin");
      if (max.trim()) p.set("pmax", String(Math.max(0, Number(max))));
      else p.delete("pmax");
    });
  }

  function sortBy(k: ListingSort) {
    update((p) => {
      const dir = tsort === k && tdir === "asc" ? "desc" : "asc";
      p.set("tsort", k);
      p.set("tdir", dir);
    });
  }

  const asOf = f?.as_of ? day(f.as_of) : "—";
  const loading = view === "cards" ? cards.isLoading : rows.isLoading;

  return (
    <AppShell search={false}>
      <div className="pg-catalog">
        <div className="phead">
          <div>
            <h1>{t.catalog.title}</h1>
            <p className="sub num">
              {cards.data || rows.data
                ? view === "cards"
                  ? t.catalog.sub(t.common.perfumes(totalCards), t.common.listings(totalListings), asOf)
                  : t.catalog.subTable(t.common.listings(totalListings), asOf)
                : t.common.loading}
            </p>
          </div>
          <div className="key" aria-label={t.common.colourKey}>
            <span className="muted">{t.common.colourKey}</span>
            {LIVE_SHOPS.map((s) => (
              <span key={s.key}>
                <i style={{ background: s.field }} />
                {s.label}
              </span>
            ))}
          </div>
        </div>

        <div className="searchrow">
          <SearchBox variant="big" live initial={search} onSubmit={(q) => setOne("q", q || null)} />
          <div className="right">
            {view === "cards" && (
              <label>
                <span className="sr">{t.catalog.sort}</span>
                <select className="sel" value={sort} onChange={(e) => setOne("sort", e.target.value === "popular" ? null : e.target.value)}>
                  {CARD_SORTS.map((s) => (
                    <option key={s} value={s}>
                      {t.catalog.sorts[s]}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="seg" role="group" aria-label={t.catalog.view}>
              <button type="button" aria-pressed={view === "cards"} onClick={() => update((p) => p.delete("view"))}>
                <LayoutGrid />
                {t.catalog.cards}
              </button>
              <button type="button" aria-pressed={view === "table"} onClick={() => update((p) => p.set("view", "table"))}>
                <Rows3 />
                {t.catalog.table}
              </button>
            </div>
            {pro && (
              <button className="btn btn-soft btn-sm" type="button" aria-pressed={picking} onClick={() => setPicking((x) => !x)} title={t.catalog.pickHint}>
                <ListChecks />
                {t.catalog.pick}
              </button>
            )}
            <ExportMenu
              path={exportAll}
              fallbackName="marketpulse_catalogue"
              header={<div className="ttl">{t.exporter.filtered(view === "cards" ? totalCards : totalListings)}</div>}
            />
          </div>
        </div>

        <div className="fbar" role="toolbar" aria-label={t.catalog.filters}>
          <div className="group">
            <span>{t.catalog.shops}</span>
            {SHOPS.map((s) => (
              <button
                key={s.key}
                className="chip"
                type="button"
                disabled={!s.live}
                title={s.live ? undefined : t.common.integrationSoon}
                aria-pressed={stores.includes(s.key)}
                onClick={() => toggleIn("shop", s.key)}
                style={{ ["--chip" as string]: s.field, ["--chip-ink" as string]: "var(--ink)" } as React.CSSProperties}
              >
                <i style={stores.includes(s.key) ? { background: "var(--ink)" } : undefined} />
                {s.label}
              </button>
            ))}
          </div>
          <div className="group">
            <span>{t.catalog.type}</span>
            {typeOpts.map((c) => (
              <button key={c.value} className="chip" type="button" aria-pressed={types.includes(c.value)} onClick={() => toggleIn("type", c.value)}>
                {c.label}
              </button>
            ))}
          </div>
          <div className="group">
            <span>{t.catalog.sizes}</span>
            {quickVols.map((v) => (
              <button key={v.value} className="chip" type="button" aria-pressed={volumes.includes(v.value)} onClick={() => toggleIn("vol", v.value)}>
                {v.label}
              </button>
            ))}
          </div>
          <button className="chip" type="button" aria-expanded={more} onClick={() => setMore((m) => !m)}>
            <SlidersHorizontal size={15} />
            {more ? t.catalog.fewerFilters : t.catalog.moreFilters}
            {extraCount > 0 && <span className="n num">{extraCount}</span>}
          </button>
        </div>

        {more && (
          <div className="more fade">
            <div className="blk vols">
              <b>{t.catalog.sizes}</b>
              <div className="vol-list">
                {volOpts.map((v) => (
                  <button key={v.value} className="chip" type="button" aria-pressed={volumes.includes(v.value)} onClick={() => toggleIn("vol", v.value)}>
                    {v.label} <span className="n num">{int(v.count)}</span>
                  </button>
                ))}
              </div>
              {(f?.volumes.length ?? 0) > commonVols.length && (
                <button className="linkish" type="button" onClick={() => setAllVols((x) => !x)} style={{ fontSize: 14 }}>
                  {allVols ? t.common.less : `${t.common.all} (${f?.volumes.length})`}
                </button>
              )}
            </div>
            <div className="blk price">
              <b>{t.catalog.price}</b>
              <form
                className="range"
                onSubmit={(e) => {
                  e.preventDefault();
                  applyPrice(minDraft, maxDraft);
                }}
              >
                <input inputMode="decimal" placeholder={t.catalog.priceMin} aria-label={t.catalog.priceMin} value={minDraft} onChange={(e) => setMinDraft(e.target.value.replace(/[^\d.]/g, ""))} onBlur={() => applyPrice(minDraft, maxDraft)} />
                <span aria-hidden="true">–</span>
                <input inputMode="decimal" placeholder={t.catalog.priceMax} aria-label={t.catalog.priceMax} value={maxDraft} onChange={(e) => setMaxDraft(e.target.value.replace(/[^\d.]/g, ""))} onBlur={() => applyPrice(minDraft, maxDraft)} />
              </form>
              <div className="presets">
                {t.catalog.presets.map((p) => (
                  <button
                    key={p.label}
                    className="chip"
                    type="button"
                    aria-pressed={priceMin === p.min && priceMax === p.max}
                    onClick={() => applyPrice(p.min?.toString() ?? "", p.max?.toString() ?? "")}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="blk brands">
              <b>{t.catalog.brands}</b>
              <div className="brand-find">
                <input type="search" placeholder={t.catalog.findBrand} aria-label={t.catalog.findBrand} value={brandQ} onChange={(e) => setBrandQ(e.target.value)} />
              </div>
              <div className="brand-list">
                {[...brands.filter((b) => !brandOpts.some((o) => o.value === b)).map((b) => ({ value: b, label: b, count: 0 })), ...brandOpts].map((b) => (
                  <button key={b.value} className="chip" type="button" aria-pressed={brands.includes(b.value)} onClick={() => toggleIn("brand", b.value)}>
                    {b.label}
                    {b.count > 0 && <span className="n num">{int(b.count)}</span>}
                  </button>
                ))}
              </div>
            </div>
            <div className="blk flags">
              <b>{t.catalog.showing}</b>
              {(
                [
                  ["stock", inStock, t.catalog.inStock, t.catalog.inStockHint],
                  ["promo", promo, t.catalog.promo, t.catalog.promoHint],
                  ["multi", multi, t.catalog.multi, t.catalog.multiHint],
                  ["dropped", dropped, t.catalog.dropped, t.catalog.droppedHint],
                ] as const
              ).map(([k, on, label, hint]) => (
                <label key={k} className="flag">
                  <input type="checkbox" checked={on} onChange={() => setOne(k, on ? null : "1")} />
                  <span>
                    {label}
                    <small>{hint}</small>
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {active.length > 0 && (
          <div className="active" aria-label={t.catalog.active}>
            {active.map((a) => (
              <button key={a.label} className="chip" type="button" onClick={a.clear} aria-label={t.catalog.remove(a.label)}>
                {a.label}
                <X />
              </button>
            ))}
            <button className="linkish" type="button" onClick={() => setSp(view === "table" ? { view: "table" } : {}, { replace: true })}>
              {t.common.clearAll}
            </button>
          </div>
        )}

        {view === "cards" ? (
          loading ? (
            <div className="grid">
              {Array.from({ length: 8 }, (_, i) => (
                <div key={i} className="skel" style={{ aspectRatio: "4 / 5" }} />
              ))}
            </div>
          ) : cards.data?.items.length ? (
            <div ref={flip} className="grid" aria-live="polite" style={{ opacity: cards.isPlaceholderData ? 0.6 : 1, transition: "opacity 200ms" }}>
              {cards.data.items.map((c, i) => (
                <Tile
                  key={c.key}
                  card={c}
                  className="fade"
                  style={{ ["--i" as string]: i } as React.CSSProperties}
                  picking={picking}
                  picked={pickedKeys.has(c.key)}
                  onPick={() =>
                    setPickedKeys((s) => {
                      const n = new Set(s);
                      if (n.has(c.key)) n.delete(c.key);
                      else n.add(c.key);
                      return n;
                    })
                  }
                />
              ))}
            </div>
          ) : (
            <div className="empty">
              <h3>{t.catalog.empty}</h3>
              <p>{t.catalog.emptyHint}</p>
            </div>
          )
        ) : (
          <div className="scroll">
            <table className="db" style={{ opacity: rows.isPlaceholderData ? 0.6 : 1 }}>
              <thead>
                <tr>
                  {picking && (
                    <th scope="col">
                      <span className="sr">{t.exporter.select}</span>
                    </th>
                  )}
                  {(
                    [
                      ["brand", t.catalog.col.brand, ""],
                      ["name", t.catalog.col.name, ""],
                      [null, t.catalog.col.type, "hide-sm"],
                      ["price", t.catalog.col.price, "r"],
                      ["change", t.catalog.col.change, "r"],
                      ["shop", t.catalog.col.shop, ""],
                      [null, t.catalog.col.status, "hide-sm"],
                    ] as [ListingSort | null, string, string][]
                  ).map(([k, label, cls]) => (
                    <th key={label} scope="col" className={cls} aria-sort={k && tsort === k ? (tdir === "asc" ? "ascending" : "descending") : undefined}>
                      {k ? (
                        <button type="button" onClick={() => sortBy(k)}>
                          {label}
                          {tsort === k ? (tdir === "asc" ? " ↑" : " ↓") : ""}
                        </button>
                      ) : (
                        label
                      )}
                    </th>
                  ))}
                  <th scope="col">
                    <span className="sr">{t.catalog.col.open}</span>
                  </th>
                </tr>
              </thead>
              <tbody ref={peek}>
                {loading &&
                  Array.from({ length: 8 }, (_, i) => (
                    <tr key={i}>
                      <td colSpan={9}>
                        <div className="skel" style={{ height: 22, borderRadius: 8 }} />
                      </td>
                    </tr>
                  ))}
                {!loading && rows.data?.items.length === 0 && (
                  <tr>
                    <td colSpan={9} className="muted" style={{ padding: "40px 12px" }}>
                      {t.catalog.empty}
                    </td>
                  </tr>
                )}
                {rows.data?.items.map((r) => {
                  const c = r.change_30d;
                  const flat = c == null || Math.abs(c) < 0.05;
                  const picked = pickedIds.has(r.product_id);
                  return (
                    <tr
                      key={r.product_id}
                      className={`link ${picked ? "picked" : ""}`}
                      data-img={r.image_url ?? undefined}
                      data-field={shopOf(r.store).field}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest("a,input,button")) return;
                        if (picking) {
                          setPickedIds((s) => {
                            const n = new Set(s);
                            if (n.has(r.product_id)) n.delete(r.product_id);
                            else n.add(r.product_id);
                            return n;
                          });
                        } else nav(`/product/${r.product_id}`);
                      }}
                    >
                      {picking && (
                        <td>
                          <input
                            type="checkbox"
                            checked={picked}
                            aria-label={`${r.brand} ${r.name}`}
                            onChange={() =>
                              setPickedIds((s) => {
                                const n = new Set(s);
                                if (n.has(r.product_id)) n.delete(r.product_id);
                                else n.add(r.product_id);
                                return n;
                              })
                            }
                          />
                        </td>
                      )}
                      <td className="brand">{r.brand}</td>
                      <td>
                        <a className="nm" href={`/product/${r.product_id}`} onClick={(e) => (e.preventDefault(), nav(`/product/${r.product_id}`))}>
                          {r.name}
                        </a>
                        {r.volume && <small className="num" style={{ fontSize: 13.5, color: "var(--muted)", marginLeft: 8 }}>{r.volume}</small>}
                      </td>
                      <td className="hide-sm">{r.concentration ?? "—"}</td>
                      <td className="r">
                        {r.old_price && r.old_price > r.price + 0.5 && <span className="old num">{eur(r.old_price)}</span>}
                        <span className="pr num">{eur(r.price)}</span>
                        {r.promo_price && (
                          <span className="promo num">
                            {r.promo_code ? t.catalog.code(r.promo_code) : t.catalog.member} {eur(r.promo_price)}
                          </span>
                        )}
                      </td>
                      <td className={`r num ${flat ? "muted" : c! < 0 ? "down" : "up"}`}>{flat ? t.common.flat : pct(c, 1)}</td>
                      <td>
                        <ShopPill store={r.store} />
                      </td>
                      <td className="hide-sm">
                        <span className={`stock ${r.in_stock ? "" : "out"}`}>
                          <i />
                          {r.in_stock ? t.common.inStock : t.common.outOfStock}
                        </span>
                      </td>
                      <td className="r">
                        <a href={r.url} target="_blank" rel="noreferrer" aria-label={`${t.common.open} ${shopOf(r.store).label}`} style={{ color: "var(--muted)" }}>
                          <ArrowUpRight size={16} />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="pager">
          <span className="num">
            {pagesTotal > 0 && t.common.pageOf(page, pagesTotal)}
            {view === "table" && rows.data ? ` · ${t.common.listings(rows.data.total)}` : ""}
          </span>
          <Pager page={page} total={pagesTotal} onPage={setPage} />
        </div>

        {picking && (
          <div className="selbar fade" role="region" aria-label={t.catalog.pick}>
            <span className="num">{pickedN ? t.exporter.selecting(pickedN) : t.catalog.pickHint}</span>
            <button
              className="btn btn-sm"
              type="button"
              style={{ background: "#2a2d31", color: "var(--bg)" }}
              onClick={() => {
                if (view === "cards") setPickedKeys((s) => new Set([...s, ...(cards.data?.items.map((c) => c.key) ?? [])]));
                else setPickedIds((s) => new Set([...s, ...(rows.data?.items.map((r) => r.product_id) ?? [])]));
              }}
            >
              {t.exporter.selectPage}
            </button>
            {pickedN > 0 && (
              <>
                <button className="linkish" type="button" onClick={() => (view === "cards" ? setPickedKeys(new Set()) : setPickedIds(new Set()))}>
                  {t.common.clear}
                </button>
                <ExportMenu path={exportPicked} fallbackName="marketpulse_selection" label={t.exporter.exportSelected} className="btn btn-accent btn-sm" />
              </>
            )}
            <button className="btn btn-white btn-sm" type="button" onClick={() => setPicking(false)}>
              {t.exporter.stop}
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
