import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Heart as HeartIcon, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, type ProductCardDetail } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useChat, usePageContext } from "@/contexts/ChatContext";
import { useFavorites } from "@/contexts/FavoritesContext";
import { useT } from "@/i18n";
import { exportUrl } from "@/lib/download";
import { day, eur, int, pctPlain } from "@/lib/format";
import { LIVE_SHOPS, fieldStyle, shopKey, shopOf } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";
import ExportMenu from "@/components/mp/ExportMenu";
import Img from "@/components/mp/Img";
import { LineChart, Legend, Ribbon } from "@/components/mp/charts";

type Range = 30 | 90 | 0;

interface Note {
  date: string;
  store: string;
  from: number | null;
  to: number | null;
  kind: "change" | "out" | "back";
}

/** Price changes per shop from the event log, newest first; gap-fill rows skipped. */
function notesOf(p: ProductCardDetail): Note[] {
  const last = new Map<string, number>();
  const out: Note[] = [];
  for (const h of p.history) {
    const s = shopKey(h.store_name ?? p.store_name);
    if (h.change_type === "synthetic") continue;
    const prev = last.get(s) ?? null;
    if (h.change_type === "out_of_stock") out.push({ date: h.parsed_at, store: s, from: prev, to: null, kind: "out" });
    else if (h.change_type === "back_in_stock") out.push({ date: h.parsed_at, store: s, from: prev, to: h.price, kind: "back" });
    else if ((h.change_type === "price_down" || h.change_type === "price_up") && prev != null && Math.abs(prev - h.price) > 0.009)
      out.push({ date: h.parsed_at, store: s, from: prev, to: h.price, kind: "change" });
    if (h.in_stock && h.price > 0) last.set(s, h.price);
  }
  return out.reverse();
}

export default function Product() {
  const t = useT();
  const { id } = useParams();
  const { user } = useAuth();
  const { ask } = useChat();
  const qc = useQueryClient();
  const { isFavorite, toggleFavorite } = useFavorites();
  const [range, setRange] = useState<Range>(90);
  const [focus, setFocus] = useState<string | null>(null);

  const q = useQuery({ queryKey: ["product", id], queryFn: () => api.getProduct(id!), enabled: !!id });
  const favs = useQuery({ queryKey: ["favorites"], queryFn: api.listFavorites });
  const p = q.data;
  const alike = useQuery({
    queryKey: ["alike", p?.brand],
    queryFn: () => api.getCards({ brands: [p!.brand!], in_stock: true, sort: "shops", limit: 7 }),
    enabled: !!p?.brand,
  });

  const offers = useMemo(() => (p ? p.offers.slice().sort((a, b) => a.price - b.price) : []), [p]);
  const best = offers[0];
  const dear = offers[offers.length - 1];
  const bestShop = best ? shopKey(best.storeName) : shopKey(p?.store_name);
  const name = p ? p.display_name || p.title : "";
  const full = p ? `${p.brand ?? ""} ${name}`.trim() : "";
  const bottleIds = p ? [p.id, ...offers.flatMap((o) => [o.product_id, ...o.variants.map((v) => v.product_id)])] : [];
  const favId = bottleIds.find((x) => isFavorite(x));
  const fav = favs.data?.find((f) => f.product_id === favId);

  usePageContext(
    p
      ? `Product page: ${full}, ${p.concentration ?? ""} ${p.volume ?? ""}; cheapest ${eur(best?.price ?? p.current_price)} at ${shopOf(bestShop).label}; ${offers.length} shops in stock`
      : "Product page",
  );

  const series = p?.series;
  const view = useMemo(() => {
    if (!series) return null;
    const n = series.days.length;
    const from = range === 0 ? 0 : Math.max(0, n - range);
    const days = series.days.slice(from);
    const shops = Object.entries(series.shops)
      .map(([k, v]) => [k, v.slice(from)] as const)
      .filter(([, v]) => v.some((x) => x != null));
    return { days, shops, cheapest: series.cheapest.slice(from) };
  }, [series, range]);

  const estimate = useMemo(() => {
    const syn = (p?.history ?? []).filter((h) => h.change_type === "synthetic").map((h) => h.parsed_at.slice(0, 10));
    if (!syn.length || !view) return null;
    syn.sort();
    const a = syn[0];
    const b = syn[syn.length - 1];
    const from = view.days.find((d) => d >= a) ?? null;
    const to = [...view.days].reverse().find((d) => d <= b) ?? null;
    return from && to && from <= to ? { from, to } : null;
  }, [p, view]);

  const stats = useMemo(() => {
    if (!view) return null;
    let low: { v: number; k: string; d: string } | null = null;
    let sum = 0;
    let cnt = 0;
    for (const [k, vals] of view.shops)
      vals.forEach((v, i) => {
        if (v == null) return;
        sum += v;
        cnt++;
        if (!low || v < low.v) low = { v, k, d: view.days[i] };
      });
    return { low: low as { v: number; k: string; d: string } | null, avg: cnt ? sum / cnt : null };
  }, [view]);

  const notes = useMemo(() => (p ? notesOf(p) : []), [p]);
  const changesInRange = view ? notes.filter((n) => n.kind === "change" && n.date.slice(0, 10) >= view.days[0]).length : 0;
  const ribbonCounts = useMemo(() => {
    const c = new Map<string, number>();
    view?.cheapest.forEach((k) => k && c.set(k, (c.get(k) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [view]);

  async function setThreshold(v: string) {
    let target = favId;
    if (!target && p) {
      target = best?.product_id ?? p.id;
      await toggleFavorite(target);
    }
    if (!target) return;
    try {
      await api.updateFavorite(target, { alert_threshold_percent: Number(v), alert_enabled: true });
      qc.invalidateQueries({ queryKey: ["favorites"] });
      toast.success(t.product.alertSaved);
    } catch {
      toast.error(t.common.error);
    }
  }

  if (q.isError) {
    return (
      <AppShell>
        <div className="empty">
          <h3>{t.product.notFound}</h3>
          <Link className="btn btn-ink" to="/catalog">
            {t.today.toCatalog}
          </Link>
        </div>
      </AppShell>
    );
  }

  if (!p) {
    return (
      <AppShell>
        <div className="pg-product">
          <div className="prod">
            <div className="window skel" style={{ border: 0 }} />
            <div className="facts">
              <div className="skel" style={{ height: 220 }} />
              <div className="skel" style={{ height: 160 }} />
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  const defTh = user?.preferences?.notification_threshold_percent ?? 5;
  const curTh = fav?.alert_threshold_percent ?? null;
  const lines = (view?.shops ?? [])
    .slice()
    .sort((a, b) => LIVE_SHOPS.findIndex((s) => s.key === a[0]) - LIVE_SHOPS.findIndex((s) => s.key === b[0]))
    .map(([k, values]) => ({ key: k, name: shopOf(k).label, color: shopOf(k).line, values, width: focus === k ? 3 : 2 }));
  // the highlighted line is drawn last so it sits on top
  if (focus) lines.sort((a, b) => (a.key === focus ? 1 : 0) - (b.key === focus ? 1 : 0));

  return (
    <AppShell>
      <div className="pg-product" key={p.id}>
        <div className="prod">
          <div className="window" style={fieldStyle(bestShop)}>
            <span className="where">{t.common.cheapestAt(shopOf(bestShop).label)}</span>
            <Img src={p.image_url} brand={p.brand ?? ""} alt={`${full} ${p.volume ?? ""}`} />
          </div>
          <div className="facts swap">
            <div>
              <p className="crumbs">
                <Link to="/catalog">{t.catalog.title}</Link> / {p.brand && <Link to={`/catalog?brand=${encodeURIComponent(p.brand)}`}>{p.brand}</Link>} / {name}
              </p>
              <p className="brand">{p.brand}</p>
              <h1 className="name">{name}</h1>
              <p className="spec">
                {[p.concentration ? t.product.conc[p.concentration] ?? p.concentration : null, p.volume, offers.length ? t.product.soldIn(offers.length, LIVE_SHOPS.length) : null].filter(Boolean).join(" · ")}
              </p>
              {p.sizes.length > 1 && (
                <div className="sizes" role="group" aria-label={t.product.sizes}>
                  {p.sizes.map((s) => {
                    const on = s.volume.replace(/\s/g, "").toLowerCase() === (p.volume ?? "").replace(/\s/g, "").toLowerCase();
                    return (
                      <Link key={s.product_id} to={`/product/${s.product_id}`} className="chip" aria-pressed={on} aria-current={on ? "page" : undefined}>
                        {s.volume} <small className="num">{eur(s.min_price)}</small>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="price-row">
              <span className="big num">{eur(best?.price ?? p.current_price)}</span>
              <span className="price-note">
                {best ? (
                  <>
                    {t.product.lowest(shopOf(bestShop).label)} {offers.length > 1 && dear ? t.product.asksMore(shopOf(dear.storeName).label, eur(dear.price - best.price)) : t.product.onlyShop}
                  </>
                ) : (
                  t.product.notInStock
                )}
              </span>
            </div>
            <div className="acts">
              {best && (
                <a className="btn btn-ink" href={best.url} target="_blank" rel="noreferrer">
                  {t.product.buyAt(shopOf(bestShop).label)} <ArrowUpRight />
                </a>
              )}
              <button
                className="btn btn-soft"
                type="button"
                aria-pressed={!!favId}
                onClick={async () => {
                  await toggleFavorite(favId ?? best?.product_id ?? p.id);
                  toast(favId ? t.common.favRemoved : t.common.favAdded);
                }}
              >
                <HeartIcon />
                {favId ? t.product.inFav : t.product.addFav}
              </button>
              <label className="alert-sel">
                {t.product.alertAt}
                <select value={curTh == null ? "" : String(curTh)} onChange={(e) => setThreshold(e.target.value || "0")}>
                  <option value="">{t.product.alertDefault(`−${defTh}%`)}</option>
                  {[5, 10, 15, 20, 30].map((v) => (
                    <option key={v} value={v}>
                      −{v}%
                    </option>
                  ))}
                </select>
              </label>
              <button className="btn btn-line btn-sm" type="button" onClick={() => ask(t.chat.aboutThis)}>
                <Sparkles />
                {t.product.askAi}
              </button>
            </div>
            <h2 className="cap">{t.product.tonight}</h2>
            <div className="rows">
              {offers.map((o, i) => {
                const k = shopKey(o.storeName);
                const win = i === 0;
                return (
                  <div key={o.product_id} className={`row ${win ? "win" : ""}`} style={fieldStyle(k)}>
                    <span className="dot" />
                    <span className="s">
                      {shopOf(k).label}
                      {o.promoPrice ? <small className="num">{o.promoCode ? t.product.withCode(o.promoCode, eur(o.promoPrice)) : t.product.member(eur(o.promoPrice))}</small> : null}
                      {o.variants.length > 0 && <small className="num">{t.product.variants(o.variants.length)}</small>}
                    </span>
                    <span className="more num">{win ? t.product.lowestTag : t.product.more(eur(o.price - best.price))}</span>
                    <span className="p num">
                      {o.previousPrice > o.price + 0.5 && <s>{eur(o.previousPrice)}</s>}
                      {eur(o.price)}
                    </span>
                    <a href={o.url} target="_blank" rel="noreferrer">
                      {t.product.open} ↗
                    </a>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {view && view.days.length > 1 && (
          <section className="hist" aria-labelledby="hist-h">
            <div className="hist-head">
              <h2 className="sec" id="hist-h">
                {t.product.history}
              </h2>
              <div className="ctl">
                <Legend items={lines.map((l) => ({ key: l.key, name: l.name, color: l.color, field: shopOf(l.key).field }))} focus={focus} onFocus={setFocus} />
                <div className="seg" role="group" aria-label={t.product.range}>
                  {([30, 90, 0] as Range[]).map((r) => (
                    <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}>
                      {r === 30 ? t.product.r30 : r === 90 ? t.product.r90 : t.product.rAll}
                    </button>
                  ))}
                </div>
                <ExportMenu
                  path={(f) => exportUrl(`/exports/products/${p.id}`, { format: f, period: range === 30 ? "1m" : range === 90 ? "3m" : "all" })}
                  fallbackName={`marketpulse_${p.id}`}
                />
              </div>
            </div>
            <p className="hint">{t.product.hint}</p>
            <LineChart
              days={view.days}
              series={lines}
              height={320}
              focus={focus}
              label={t.product.chartLabel(full, view.days.length)}
              estimate={estimate}
              estimateLabel={t.common.estimate}
              xTicks={view.days.length > 60 ? 5 : 4}
            />
            {estimate && <p className="hint" style={{ margin: "10px 0 0 48px" }}>{t.common.estimateNote}</p>}
            <div className="ribbon-wrap">
              <p>{t.product.ribbonH}</p>
              <Ribbon cheapest={view.cheapest} label={ribbonCounts.map(([k, n]) => t.product.ribbonSum(shopOf(k).label, n)).join(" · ")} />
              <div className="ribbon-key num">
                <span>{day(view.days[0])}</span>
                <span>{ribbonCounts.map(([k, n]) => t.product.ribbonSum(shopOf(k).label, n)).join(" · ")}</span>
                <span>{day(view.days[view.days.length - 1])}</span>
              </div>
            </div>
            <div className="stats">
              {stats?.low && (
                <div className="stat">
                  <b className="num">{eur(stats.low.v)}</b>
                  <span>{t.product.sLowest(shopOf(stats.low.k).label, day(stats.low.d))}</span>
                </div>
              )}
              <div className="stat">
                <b className="num">{eur(stats?.avg)}</b>
                <span>{t.product.sAvg}</span>
              </div>
              <div className="stat">
                <b className="num">{best && dear ? eur(dear.price - best.price) : "—"}</b>
                <span>
                  {t.product.sGap}
                  {best && dear && dear.price > best.price ? ` (${pctPlain(((dear.price - best.price) / best.price) * 100)})` : ""}
                </span>
              </div>
              <div className="stat">
                <b className="num">{int(changesInRange)}</b>
                <span>{t.product.sChanges(day(view.days[0]))}</span>
              </div>
            </div>
          </section>
        )}

        <div className="lower">
          <section className="notes" aria-labelledby="notes-h">
            <h3 id="notes-h">{t.product.notes}</h3>
            {notes.length ? (
              notes.slice(0, 8).map((n, i) => {
                const c = n.from != null && n.to != null ? n.to - n.from : null;
                return (
                  <div key={i} className="ev">
                    <span className="d num">{day(n.date)}</span>
                    <span>
                      <span className="pill" style={fieldStyle(n.store)}>
                        {shopOf(n.store).label}
                      </span>{" "}
                      <span className="num muted">
                        {n.kind === "out" ? t.product.outOfStock : n.kind === "back" ? `${t.product.backInStock} · ${eur(n.to)}` : `${eur(n.from)} → ${eur(n.to)}`}
                      </span>
                    </span>
                    <span className={`c num ${c == null ? "muted" : c < 0 ? "down" : "up"}`}>{n.kind === "change" && c != null ? `${c > 0 ? "+" : "−"}${eur(Math.abs(c))}` : ""}</span>
                  </div>
                );
              })
            ) : (
              <p className="muted">{t.product.noNotes}</p>
            )}
          </section>
          {alike.data && alike.data.items.filter((c) => !bottleIds.includes(c.product_id)).length > 0 && (
            <section className="alike" aria-labelledby="alike-h">
              <h3 id="alike-h">{t.product.alike(p.brand ?? "")}</h3>
              <div className="alike-grid">
                {alike.data.items
                  .filter((c) => !bottleIds.includes(c.product_id))
                  .slice(0, 6)
                  .map((c) => (
                    <Link key={c.key} className="mini" to={`/product/${c.product_id}`} style={fieldStyle(c.cheapest_store)}>
                      <span className="pic">
                        <Img src={c.image_url} brand={c.brand} />
                      </span>
                      <span>
                        <b>{c.name}</b>
                        <small>{[c.concentration, c.volume].filter(Boolean).join(" · ")}</small>
                        <span className="pp num">{eur(c.min_price)}</span>
                      </span>
                    </Link>
                  ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </AppShell>
  );
}
