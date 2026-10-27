import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type CatalogCard, type MoveItem } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import { day, eur, eur0, int, pct, pctPlain } from "@/lib/format";
import { PRO_PRICE } from "@/lib/plan";
import { fieldStyle, shopOf } from "@/lib/shops";
import Img from "@/components/mp/Img";
import LangSwitch from "@/components/mp/LangSwitch";
import SearchBox, { spec } from "@/components/mp/SearchBox";
import Tile from "@/components/mp/Tile";
import usePeek from "@/components/mp/usePeek";

function sorted(card: CatalogCard) {
  const live = card.offers.filter((o) => o.in_stock);
  return (live.length ? live : card.offers).slice().sort((a, b) => a.price - b.price);
}

function Drop({ m }: { m: MoveItem }) {
  const t = useT();
  return (
    <Link className="drop" to={`/product/${m.product_id}`} style={fieldStyle(m.store)}>
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

export default function Landing() {
  const t = useT();
  const { user } = useAuth();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["landing"], queryFn: api.getLanding, staleTime: 10 * 60_000 });
  const [th, setTh] = useState(10);
  const peek = usePeek<HTMLOListElement>();

  const m = data?.market;
  const asOf = m?.as_of ? day(m.as_of) : "—";
  const hero = data?.hero;
  const rows = hero ? sorted(hero) : [];
  const best = rows[0];
  const dear = rows[rows.length - 1];
  const start = user ? "/today" : "/register";
  const shares = useMemo(() => (m ? m.shops.filter((s) => s.cheapest_count > 0).sort((a, b) => b.cheapest_share - a.cheapest_share) : []), [m]);
  const msgs = (data?.drops ?? []).filter((d) => -d.change_percent >= th).slice(0, 2);

  return (
    <div className="pg-landing">
      <div className="wrap">
        <header className="nav">
          <nav className="nav-l" aria-label={t.shell.mainNav}>
            <Link to={user ? "/catalog" : "/signin"}>{t.landing.navCatalog}</Link>
            <a href="#gaps">{t.landing.navGaps}</a>
            <a href="#pro">{t.landing.navPro}</a>
          </nav>
          <Link className="logo" to="/">
            MarketPulse
          </Link>
          <div className="nav-r">
            <LangSwitch />
            {user ? (
              <Link className="btn btn-ink" to="/today">
                {t.landing.openApp}
              </Link>
            ) : (
              <>
                <Link className="plain" to="/signin">
                  {t.landing.signIn}
                </Link>
                <Link className="btn btn-ink" to="/register">
                  {t.landing.start}
                </Link>
              </>
            )}
          </div>
        </header>

        <main>
          <section className="hero" aria-labelledby="hero-h">
            <div className="hero-copy">
              <h1 className="display" id="hero-h">
                <span className="line">
                  <span style={{ ["--i" as string]: 0 } as React.CSSProperties}>{t.landing.heroA(hero?.brand ?? "Chanel")}</span>
                </span>
                <span className="line">
                  <span style={{ ["--i" as string]: 1 } as React.CSSProperties}>
                    {t.landing.heroB(best && dear ? eur0(Math.floor(dear.price - best.price)) : "€86")}
                  </span>
                </span>
              </h1>
              <p className="lead rise" style={{ ["--i" as string]: 3 } as React.CSSProperties}>
                {t.landing.lead(m ? int(m.current_products) : "20,000")}
              </p>
              <div className="rise" style={{ ["--i" as string]: 4, width: "min(100%, 560px)" } as React.CSSProperties}>
                {user ? (
                  <SearchBox variant="hero" />
                ) : (
                  <div className="search">
                    <form
                      role="search"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const q = new FormData(e.currentTarget).get("q")?.toString().trim() ?? "";
                        nav(`/register?next=${encodeURIComponent(`/catalog${q ? `?q=${encodeURIComponent(q)}` : ""}`)}`);
                      }}
                    >
                      <input name="q" type="search" autoComplete="off" placeholder={t.landing.find} aria-label={t.landing.find} />
                      <button className="btn btn-accent" type="submit">
                        {t.landing.compare}
                      </button>
                    </form>
                  </div>
                )}
                <p className="search-note">{t.landing.searchNote}</p>
              </div>
            </div>
            <div className="stage">
              {hero && best && (
                <>
                  <Link className="stage-tile" to={user ? `/product/${hero.product_id}` : "/register"} style={fieldStyle(best.store)}>
                    <div className="stage-top">
                      <span>{t.landing.cheapestAt(shopOf(best.store).label)}</span>
                      {dear && dear !== best && <span>{t.landing.moreAt(pct(((dear.price - best.price) / best.price) * 100), shopOf(dear.store).label)}</span>}
                    </div>
                    <Img src={hero.image_url} brand={hero.brand} alt={`${hero.brand} ${hero.name} ${spec(hero)}`} />
                  </Link>
                  <div className="label rise" style={{ ["--i" as string]: 6 } as React.CSSProperties}>
                    <div className="label-h">{hero.name}</div>
                    <div className="label-sub">
                      {hero.brand} · {spec(hero)} · {t.landing.scanOf(asOf)}
                    </div>
                    {rows.map((o) => (
                      <div key={o.product_id} className="lrow" style={fieldStyle(o.store)}>
                        <i />
                        <span>{shopOf(o.store).label}</span>
                        <b className="num">{eur(o.price)}</b>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </section>

          {data && data.shelf.length > 0 && (
            <section className="block" aria-labelledby="shelf-h">
              <div className="head-row reveal">
                <h2 className="head" id="shelf-h">
                  {t.landing.shelfH}
                </h2>
                <p>{t.landing.shelfP(asOf)}</p>
              </div>
              <div className="shelf">
                {data.shelf.map((c, i) => (
                  <Tile key={c.key} card={c} className="deal" style={{ ["--i" as string]: i } as React.CSSProperties} />
                ))}
              </div>
            </section>
          )}

          {data && data.gaps.length > 0 && (
            <section className="block" id="gaps" aria-labelledby="gaps-h">
              <div className="head-row reveal">
                <h2 className="head" id="gaps-h">
                  {t.landing.gapsH}
                </h2>
                <p>{t.landing.gapsP}</p>
              </div>
              <ol className="index" ref={peek}>
                {data.gaps.map((c) => {
                  const r = sorted(c);
                  const lo = r[0];
                  const hi = r[r.length - 1];
                  return (
                    <li key={c.key}>
                      <Link className="ix" to={user ? `/product/${c.product_id}` : "/register"} data-img={c.image_url ?? undefined} data-field={shopOf(lo.store).field}>
                        <span className="ix-thumb" style={fieldStyle(lo.store)}>
                          <Img src={c.image_url} brand={c.brand} />
                        </span>
                        <span className="ix-name">
                          {c.brand} {c.name}
                          <small>{spec(c)}</small>
                        </span>
                        <span className="ix-shops num">
                          <span className="l">
                            <span className="pill" style={fieldStyle(lo.store)}>
                              {shopOf(lo.store).label}
                            </span>
                            {eur(lo.price)}
                          </span>
                          <span className="l muted">
                            <span className="pill">{shopOf(hi.store).label}</span>
                            {eur(hi.price)}
                          </span>
                        </span>
                        <span className="ix-gap num">
                          {pctPlain(((hi.price - lo.price) / lo.price) * 100)}
                          <small>{t.landing.more(eur(hi.price - lo.price))}</small>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </section>
          )}

          {data && data.drops.length > 0 && (
            <section className="block" aria-labelledby="drops-h">
              <div className="head-row reveal">
                <h2 className="head" id="drops-h">
                  {t.landing.dropsH}
                </h2>
                <p>{t.landing.dropsP}</p>
              </div>
              <div className="drops">
                {data.drops.slice(0, 6).map((d) => (
                  <Drop key={`${d.product_id}-${d.store}`} m={d} />
                ))}
              </div>
            </section>
          )}

          {m && shares.length > 0 && (
            <section className="block" aria-labelledby="share-h">
              <div className="head-row reveal">
                <h2 className="head" id="share-h">
                  {t.landing.shareH}
                </h2>
                <p>{t.landing.shareP(int(m.comparable))}</p>
              </div>
              <div className="shares">
                {shares.map((s) => (
                  <div key={s.store} className="share" style={fieldStyle(s.store)}>
                    <b>{s.store_name}</b>
                    <div>
                      <div className="fig num">
                        {s.cheapest_share.toFixed(1).replace(/\.0$/, "")}
                        <small>%</small>
                      </div>
                      <p>{t.landing.cheapestFor(int(s.cheapest_count))}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="spread-line reveal">
                <p>
                  {t.landing.spreadA} <b className="num">{pctPlain(m.spread_median, 1)}</b> {t.landing.spreadB}
                </p>
                <p>{t.landing.spreadNote}</p>
              </div>
            </section>
          )}

          <section className="block" id="pro" aria-labelledby="pro-h">
            <div className="head-row reveal">
              <h2 className="head" id="pro-h">
                {t.landing.plansH}
              </h2>
              <p>{t.landing.plansP}</p>
            </div>
            <div className="plans">
              <div className="plan free">
                <h3>{t.landing.free}</h3>
                <div className="price">{t.landing.freePrice}</div>
                <ul>
                  {t.landing.freeList.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
                <Link className="btn btn-soft" to={start}>
                  {t.landing.start}
                </Link>
              </div>
              <div className="plan pro">
                <h3>
                  Pro <span className="tag tag-pro">{t.landing.proBadge}</span>
                </h3>
                <div className="price num">
                  {eur(PRO_PRICE)}
                  <small>{t.landing.perMonth}</small>
                </div>
                <div className="cols">
                  <ul>
                    {t.landing.proList.map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                  {m && (
                    <div className="mini-kpis">
                      {[
                        ["notino", int(m.changes_7d), t.landing.mk.changes],
                        ["220", pctPlain(m.spread_median, 1), t.landing.mk.gap],
                        ["makeup", int(m.comparable), t.landing.mk.matched],
                        ["douglas", int(m.history_rows), t.landing.mk.rows(m.history_since ? day(m.history_since) : "May")],
                      ].map(([s, v, l]) => (
                        <div key={s} className="mk" style={fieldStyle(s)}>
                          <b className="num">{v}</b>
                          <span>{l}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <Link className="btn btn-accent" to={user ? "/analytics" : "/register"}>
                  {t.landing.seeAnalytics}
                </Link>
              </div>
            </div>
          </section>
        </main>
      </div>

      <section className="night" aria-labelledby="al-h">
        <div className="wrap night-grid">
          <div className="night-copy reveal">
            <h2 className="head" id="al-h">
              {t.landing.alertsH}
            </h2>
            <p>{t.landing.alertsP}</p>
            <div className="th" role="radiogroup" aria-label={t.landing.dropsOf}>
              <span>{t.landing.dropsOf}</span>
              {[5, 10, 20].map((v) => (
                <label key={v}>
                  <input type="radio" name="th" value={v} checked={th === v} onChange={() => setTh(v)} />
                  <i>{v}%</i>
                </label>
              ))}
            </div>
            <Link className="btn btn-white" to={user ? "/favorites" : "/register"}>
              {t.landing.alertsCta}
            </Link>
          </div>
          <div className="msgs" aria-live="polite">
            {msgs.length ? (
              msgs.map((d) => (
                <div key={`${d.product_id}-${d.store}`} className="msg" style={fieldStyle(d.store)}>
                  <div className="pic">
                    <Img src={d.image_url} brand={d.brand} />
                  </div>
                  <div>
                    <div className="from">
                      <span>{t.landing.msgFrom}</span>
                      <span>04:12</span>
                    </div>
                    <div className="txt">
                      {t.landing.msgText(`${d.brand} ${d.name}`, pctPlain(Math.abs(d.change_percent)), shopOf(d.store).label)}
                      <small className="num">
                        {eur(d.old_price)} → {eur(d.new_price)}, {spec(d)}
                      </small>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p style={{ color: "#9a9a95" }}>{t.landing.noMsg}</p>
            )}
          </div>
        </div>
      </section>

      <div className="wrap">
        <section className="close" aria-labelledby="close-h">
          <h2 className="display" id="close-h">
            {t.landing.closeH}
          </h2>
          <Link className="btn btn-accent" to={start}>
            {user ? t.landing.openApp : t.landing.closeCta}
          </Link>
        </section>
        <footer className="foot">
          <span>{t.landing.foot}</span>
          <span>{t.landing.footScan(asOf)}</span>
        </footer>
      </div>
    </div>
  );
}
