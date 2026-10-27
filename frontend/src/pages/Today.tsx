import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type FavoriteItem, type MoveItem } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useChat, usePageContext } from "@/contexts/ChatContext";
import { useT } from "@/i18n";
import { day, eur, int, pct, pctPlain } from "@/lib/format";
import { fieldStyle, shopOf } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";
import Img from "@/components/mp/Img";
import { spec } from "@/components/mp/SearchBox";
import Tile from "@/components/mp/Tile";

function DropCard({ m, i }: { m: MoveItem; i: number }) {
  const t = useT();
  return (
    <Link className="drop deal" to={`/product/${m.product_id}`} style={{ ...fieldStyle(m.store), ["--i" as string]: i } as React.CSSProperties}>
      <div className="drop-copy">
        <div>
          <div className="drop-fig num">{pct(m.change_percent)}</div>
          <div style={{ marginTop: 10, fontWeight: 500 }}>{t.landing.atShop(shopOf(m.store).label)}</div>
        </div>
        <div>
          <div className="drop-name">
            {m.brand}
            <span>
              {m.name} · {spec(m)}
            </span>
          </div>
          <div className="num" style={{ marginTop: 8, fontSize: 15 }}>
            <s>{eur(m.old_price)}</s> {eur(m.new_price)}
          </div>
        </div>
      </div>
      <div className="drop-pic">
        <Img src={m.image_url} brand={m.brand} alt={`${m.brand} ${m.name}`} />
      </div>
    </Link>
  );
}

function FavRow({ f }: { f: FavoriteItem }) {
  const t = useT();
  const best = f.offers.find((o) => o.is_available) ?? f.offers[0];
  const c = f.change_30d;
  const steady = c == null || Math.abs(c) < 0.5;
  return (
    <Link className="chg" to={`/product/${f.product_id}`}>
      <span className="pic" style={fieldStyle(best?.store ?? f.store_name)}>
        <Img src={f.image_url} brand={f.brand ?? ""} />
      </span>
      <span style={{ minWidth: 0 }}>
        <b>
          {f.brand} {f.display_name ?? f.title}
        </b>
        <small>
          {spec(f)}
          {best ? ` · ${t.today.cheapestNow(shopOf(best.store).label)}` : ""}
        </small>
      </span>
      <span className="p num">{eur(best?.price ?? f.current_price)}</span>
      <span className={`c num ${steady ? "muted" : c! < 0 ? "down" : "up"}`}>{steady ? t.today.steadyN : `${pct(c, 1)} · 30d`}</span>
    </Link>
  );
}

export default function Today() {
  const t = useT();
  const { user } = useAuth();
  const { ask, setOpen } = useChat();
  usePageContext("Today page: recent price drops in the user's shops and brands, and changes on their favorites list");
  const prefs = user?.preferences;
  const stores = prefs?.monitored_stores?.length ? prefs.monitored_stores : undefined;
  const brands = prefs?.interested_brands?.length ? prefs.interested_brands : undefined;
  const [mine, setMine] = useState(!!brands);

  const landing = useQuery({ queryKey: ["landing"], queryFn: api.getLanding, staleTime: 10 * 60_000 });
  const favs = useQuery({ queryKey: ["favorites"], queryFn: api.listFavorites });
  const drops = useQuery({
    queryKey: ["drops", stores, mine ? brands : null],
    queryFn: () => api.getDrops({ days: 7, stores, brands: mine ? brands : undefined, limit: 9 }),
  });
  const picks = useQuery({
    queryKey: ["today-picks", stores],
    queryFn: () => api.getCards({ sort: "drop", multi_shop: true, dropped: true, in_stock: true, stores, limit: 8 }),
  });

  const name = user?.full_name?.trim().split(/\s+/)[0] || user?.email.split("@")[0] || "";
  const h = new Date().getHours();
  const hello = h < 12 ? t.today.morning(name) : h < 18 ? t.today.afternoon(name) : t.today.evening(name);
  const m = landing.data?.market;
  const favList = useMemo(() => favs.data ?? [], [favs.data]);
  const cheaper = favList.filter((f) => f.price_when_added && f.current_price < f.price_when_added - 0.005).length;
  const topDrop = drops.data?.[0];
  const changes = useMemo(
    () =>
      favList
        .slice()
        .sort((a, b) => Math.abs(b.change_30d ?? 0) - Math.abs(a.change_30d ?? 0))
        .slice(0, 6),
    [favList],
  );

  return (
    <AppShell>
      <div className="pg-today">
        <section className="hello">
          <h1 className="rise">{hello}</h1>
          <p className="rise" style={{ ["--i" as string]: 1 } as React.CSSProperties}>
            {t.today.sub(m?.as_of ? day(m.as_of) : "—")}
          </p>
        </section>

        <section className="kpis" aria-label={t.shell.nav.today}>
          <Link className="kpi rise" to="/favorites" style={{ ["--i" as string]: 1 } as React.CSSProperties}>
            <span className="l">{t.today.kFav}</span>
            <div>
              <div className="v num">{int(favList.length)}</div>
              <div className="n">{t.today.kFavN(cheaper)}</div>
            </div>
          </Link>
          <Link className="kpi rise" to={topDrop ? `/product/${topDrop.product_id}` : "/catalog"} style={{ ["--i" as string]: 2, ...(topDrop ? fieldStyle(topDrop.store) : {}), background: topDrop ? "var(--field)" : undefined } as React.CSSProperties}>
            <span className="l">{t.today.kDrop}</span>
            <div>
              <div className="v num">{topDrop ? pct(topDrop.change_percent) : "—"}</div>
              <div className="n" style={{ color: "var(--ink)" }}>{topDrop ? t.today.kDropN(`${topDrop.brand} ${topDrop.name}`, shopOf(topDrop.store).label) : ""}</div>
            </div>
          </Link>
          <div className="kpi rise" style={{ ["--i" as string]: 3 } as React.CSSProperties}>
            <span className="l">{t.today.kChanges}</span>
            <div>
              <div className="v num">{m ? int(m.changes_7d) : "—"}</div>
              <div className="n">{t.today.kChangesN}</div>
            </div>
          </div>
          <Link className="kpi ink rise" to="/analytics" style={{ ["--i" as string]: 4 } as React.CSSProperties}>
            <span className="l">{t.today.kGap}</span>
            <div>
              <div className="v num">{m ? pctPlain(m.spread_median, 1) : "—"}</div>
              <div className="n">{t.today.kGapN}</div>
            </div>
          </Link>
        </section>

        <section className="sec" aria-labelledby="drops-h">
          <div className="sec-head">
            <div>
              <h2 className="h2" id="drops-h">
                {t.today.dropsH}
              </h2>
              <p>{t.today.dropsP}</p>
            </div>
            <div className="scope">
              <span>{t.today.scope}</span>
              {stores ? stores.map((s) => <span key={s} className="pill" style={fieldStyle(s)}>{shopOf(s).label}</span>) : <span>{t.today.allShops}</span>}
              {brands && (
                <div className="seg" role="group" style={{ marginLeft: 6 }}>
                  <button type="button" aria-pressed={mine} onClick={() => setMine(true)}>
                    {t.today.yourBrands}
                  </button>
                  <button type="button" aria-pressed={!mine} onClick={() => setMine(false)}>
                    {t.today.allBrands}
                  </button>
                </div>
              )}
              <Link className="linkish" to="/profile#shops" style={{ marginLeft: 6 }}>
                {t.today.editScope}
              </Link>
            </div>
          </div>
          {drops.isLoading ? (
            <div className="drops">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skel" style={{ minHeight: 230 }} />
              ))}
            </div>
          ) : drops.data?.length ? (
            <div className="drops">
              {drops.data.map((d, i) => (
                <DropCard key={`${d.product_id}-${d.store}`} m={d} i={i} />
              ))}
            </div>
          ) : (
            <div className="empty">
              <p>{t.today.noDrops}</p>
              {mine && brands && (
                <button className="btn btn-soft btn-sm" type="button" onClick={() => setMine(false)}>
                  {t.today.allBrands}
                </button>
              )}
            </div>
          )}
        </section>

        <section className="sec" aria-labelledby="fav-h">
          <div className="sec-head">
            <div>
              <h2 className="h2" id="fav-h">
                {t.today.favH}
              </h2>
              <p>{t.today.favP}</p>
            </div>
            {favList.length > 0 && (
              <Link className="btn btn-soft btn-sm" to="/favorites">
                {t.today.allFav}
              </Link>
            )}
          </div>
          {favs.isLoading ? (
            <div className="changes">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skel" style={{ height: 96 }} />
              ))}
            </div>
          ) : changes.length ? (
            <div className="changes">
              {changes.map((f) => (
                <FavRow key={f.id} f={f} />
              ))}
            </div>
          ) : (
            <div className="empty card">
              <p>{t.today.favEmpty}</p>
              <Link className="btn btn-ink" to="/catalog">
                {t.today.toCatalog}
              </Link>
            </div>
          )}
        </section>

        {picks.data && picks.data.items.length > 0 && (
          <section className="sec" aria-labelledby="pick-h">
            <div className="sec-head">
              <div>
                <h2 className="h2" id="pick-h">
                  {t.today.pickH}
                </h2>
                <p>{t.today.pickP}</p>
              </div>
              <Link className="btn btn-soft btn-sm" to={`/catalog?sort=drop&multi=1&dropped=1${stores ? `&shops=${stores.join(",")}` : ""}`}>
                {t.today.seeAll}
              </Link>
            </div>
            <div className="grid">
              {picks.data.items.map((c, i) => (
                <Tile key={c.key} card={c} className="deal" style={{ ["--i" as string]: i } as React.CSSProperties} />
              ))}
            </div>
          </section>
        )}

        <section className="sec">
          <div className="askbar">
            <div>
              <h2 className="h2">{t.today.askH}</h2>
              <p>{t.today.askP}</p>
              <div className="chat-s" style={{ marginTop: 16 }}>
                {t.chat.starters.map((s) => (
                  <button key={s} type="button" onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <button className="btn btn-white" type="button" onClick={() => setOpen(true)}>
              {t.today.askCta}
            </button>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
