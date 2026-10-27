import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type MoveItem } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { usePageContext } from "@/contexts/ChatContext";
import { useT } from "@/i18n";
import { exportUrl } from "@/lib/download";
import { day, eur, eur0, int, num, pct, pctPlain } from "@/lib/format";
import { hasPro } from "@/lib/plan";
import { LIVE_SHOPS, fieldStyle, shopOf } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";
import ExportMenu from "@/components/mp/ExportMenu";
import Img from "@/components/mp/Img";
import ProGate from "@/components/mp/ProGate";
import { spec } from "@/components/mp/SearchBox";
import usePeek from "@/components/mp/usePeek";
import { ActivityBars, Histogram, Legend, LineChart } from "@/components/mp/charts";

type Range = 7 | 30 | 90;
const SECTIONS = ["all", "overview", "shops", "index", "activity", "drops", "rises", "gaps", "brands", "bands"] as const;
type Section = (typeof SECTIONS)[number];
const BAND_EDGES = [0, 25, 50, 75, 100, 150, 200];

function Move({ m }: { m: MoveItem }) {
  return (
    <li>
      <Link className="mv" to={`/product/${m.product_id}`}>
        <span className="mv-pic" style={fieldStyle(m.store)}>
          <Img src={m.image_url} brand={m.brand} />
        </span>
        <span className="mv-t">
          <b>
            {m.brand} {m.name}
          </b>
          <small className="num">
            <span className="pill" style={fieldStyle(m.store)}>
              {shopOf(m.store).label}
            </span>
            {spec(m)}
            <span>
              <s>{eur(m.old_price)}</s> {eur(m.new_price)}
            </span>
          </small>
        </span>
        <span className={`mv-p num ${m.change_percent < 0 ? "down" : "up"}`}>{pct(m.change_percent)}</span>
      </Link>
    </li>
  );
}

function Head({ kicker, title, text, id, tools }: { kicker: string; title: string; text?: string; id: string; tools?: React.ReactNode }) {
  return (
    <div className="sec-head">
      <h2 className="h2" id={id}>
        <small>{kicker}</small>
        {title}
      </h2>
      {tools ? <div className="tools">{tools}</div> : text ? <p>{text}</p> : null}
    </div>
  );
}

function ProAnalytics() {
  const t = useT();
  const [range, setRange] = useState<Range>(30);
  const [section, setSection] = useState<Section>("all");
  const [focus, setFocus] = useState<string | null>(null);
  const peek = usePeek<HTMLTableSectionElement>();
  const idxDays = range === 7 ? 14 : range;

  const overview = useQuery({ queryKey: ["an-overview"], queryFn: api.analytics.overview, staleTime: 5 * 60_000 });
  const index = useQuery({ queryKey: ["an-index", idxDays], queryFn: () => api.analytics.priceIndex(idxDays), staleTime: 5 * 60_000 });
  const activity = useQuery({ queryKey: ["an-activity", range], queryFn: () => api.analytics.activity(Math.max(7, range)), staleTime: 5 * 60_000 });
  const dist = useQuery({ queryKey: ["an-dist", range], queryFn: () => api.analytics.distribution(Math.max(7, range)), staleTime: 5 * 60_000 });
  const drops = useQuery({ queryKey: ["an-drops", range], queryFn: () => api.analytics.moves(range, "down", 10), staleTime: 5 * 60_000 });
  const rises = useQuery({ queryKey: ["an-rises", range], queryFn: () => api.analytics.moves(range, "up", 10), staleTime: 5 * 60_000 });
  const gaps = useQuery({ queryKey: ["an-gaps"], queryFn: () => api.analytics.gaps(15), staleTime: 5 * 60_000 });
  const heat = useQuery({ queryKey: ["an-heat"], queryFn: () => api.analytics.brandShop(12), staleTime: 5 * 60_000 });
  const bands = useQuery({ queryKey: ["an-bands"], queryFn: api.analytics.priceBands, staleTime: 5 * 60_000 });

  const m = overview.data;
  usePageContext(`Market analytics page (Pro), period ${range} days${m ? `; median gap between shops ${m.spread_median}%` : ""}`);

  const shops = useMemo(() => (m ? m.shops.filter((s) => s.products > 0).sort((a, b) => b.cheapest_share - a.cheapest_share) : []), [m]);
  const actDays = useMemo(() => {
    const ds = [...new Set((activity.data ?? []).map((p) => p.date))].sort();
    if (!ds.length) return [];
    const end = new Date(ds[ds.length - 1] + "T12:00:00Z");
    return Array.from({ length: Math.max(7, range) }, (_, i) => {
      const d = new Date(end);
      d.setUTCDate(end.getUTCDate() - (Math.max(7, range) - 1 - i));
      return d.toISOString().slice(0, 10);
    });
  }, [activity.data, range]);
  const actStores = LIVE_SHOPS.map((s) => s.key).filter((k) => (activity.data ?? []).some((p) => p.store === k));

  const idx = index.data;
  const idxLines = idx
    ? LIVE_SHOPS.filter((s) => idx.shops[s.key])
        .map((s) => ({ key: s.key, name: s.label, color: s.line, values: idx.shops[s.key], width: focus === s.key ? 3 : 2 }))
        .sort((a, b) => (a.key === focus ? 1 : 0) - (b.key === focus ? 1 : 0))
    : [];

  const heatMax = Math.max(1, ...(heat.data?.cells ?? []).map((c) => c.premium));
  const bandsBy = useMemo(() => {
    const out = new Map<string, number[]>();
    (bands.data ?? []).forEach((r) => {
      if (!out.has(r.store)) out.set(r.store, Array(BAND_EDGES.length).fill(0));
      out.get(r.store)![r.band] = r.count;
    });
    return [...out.entries()].sort((a, b) => LIVE_SHOPS.findIndex((s) => s.key === a[0]) - LIVE_SHOPS.findIndex((s) => s.key === b[0]));
  }, [bands.data]);
  const bandLabel = (i: number) => (i < BAND_EDGES.length - 1 ? `${eur0(BAND_EDGES[i])}–${eur0(BAND_EDGES[i + 1])}` : `${eur0(BAND_EDGES[i])}+`);

  return (
    <div className="pg-an">
      <section className="phead">
        <div>
          <h1>{t.analytics.title}</h1>
          <p className="sub">{t.analytics.sub(m?.as_of ? day(m.as_of) : "—")}</p>
        </div>
        <div className="ctrls">
          <div className="seg" role="group" aria-label={t.analytics.period}>
            {([7, 30, 90] as Range[]).map((r) => (
              <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}>
                {t.analytics.days(r)}
              </button>
            ))}
          </div>
          <ExportMenu
            className="btn btn-ink btn-sm"
            path={(f) => exportUrl("/exports/analytics", { format: f, days: range, section: section === "all" ? undefined : section })}
            fallbackName="marketpulse_analytics"
            header={
              <label className="ttl" style={{ display: "grid", gap: 6, textTransform: "none", letterSpacing: 0 }}>
                {t.exporter.section}
                <select className="sel" value={section} onChange={(e) => setSection(e.target.value as Section)} style={{ background: "var(--bg)", color: "var(--ink)" }}>
                  {SECTIONS.map((s) => (
                    <option key={s} value={s}>
                      {t.exporter.sections[s]}
                    </option>
                  ))}
                </select>
              </label>
            }
          />
        </div>
      </section>

      <section className="kpis" aria-label={t.analytics.title}>
        {m
          ? [
              [t.analytics.k.tracked, int(m.current_products), t.analytics.k.trackedN(int(m.total_products))],
              [t.analytics.k.comparable, int(m.comparable), t.analytics.k.comparableN],
              [t.analytics.k.changes7, int(m.changes_7d), t.analytics.k.changesN],
              [t.analytics.k.changes30, int(m.changes_30d), t.analytics.k.changesN],
              [t.analytics.k.spread, pctPlain(m.spread_median, 1), t.analytics.k.spreadN(pctPlain(m.spread_mean, 1))],
              [t.analytics.k.rows, int(m.history_rows), t.analytics.k.rowsN(m.history_since ? day(m.history_since) : "—")],
            ].map(([l, v, n], i) => (
              <div key={l} className="kpi rise" style={{ ["--i" as string]: i } as React.CSSProperties}>
                <span className="kpi-l">{l}</span>
                <div>
                  <div className="kpi-v num">{v}</div>
                  <div className="kpi-n">{n}</div>
                </div>
              </div>
            ))
          : Array.from({ length: 6 }, (_, i) => <div key={i} className="skel" style={{ minHeight: 150 }} />)}
      </section>

      <section className="sec" aria-labelledby="idx-h">
        <Head kicker={t.analytics.indexKicker} title={t.analytics.indexH} text={t.analytics.indexP} id="idx-h" />
        <div className="panel">
          <div className="panel-h">
            <Legend
              items={idxLines.map((l) => ({ key: l.key, name: l.name, color: l.color, field: shopOf(l.key).field, extra: idx ? <small className="num muted">· {int(idx.basket[l.key])}</small> : null }))}
              focus={focus}
              onFocus={setFocus}
            />
            {idx && <small className="num">{t.analytics.basket(int(Object.values(idx.basket).reduce((a, b) => a + b, 0)))}</small>}
          </div>
          {idx ? (
            <LineChart
              days={idx.days}
              series={idxLines}
              height={340}
              focus={focus}
              baseline={100}
              yFormat={(v) => num(v, 0)}
              tipFormat={(v) => num(v, 1)}
              tipOrder="desc"
              label={t.analytics.indexLabel(idx.days.length)}
              estimate={idx.estimated_from || idx.estimated_to ? { from: idx.estimated_from, to: idx.estimated_to } : null}
              estimateLabel={t.common.estimate}
              xTicks={5}
            />
          ) : (
            <div className="skel" style={{ height: 340 }} />
          )}
          {idx && (idx.estimated_from || idx.estimated_to) && <p className="note">{t.common.estimateNote}</p>}
        </div>
      </section>

      <section className="sec" aria-labelledby="who-h">
        <Head kicker={t.analytics.whoKicker} title={t.analytics.whoH} text={m ? t.analytics.whoP(int(m.comparable)) : ""} id="who-h" />
        {m && (
          <>
            <div className="share" role="img" aria-label={shops.map((s) => `${s.store_name} ${s.cheapest_share}%`).join(", ")}>
              {shops
                .filter((s) => s.cheapest_share > 0)
                .map((s) => (
                  <span key={s.store} style={{ ...fieldStyle(s.store), flexGrow: s.cheapest_share, flexBasis: 0 }}>
                    {s.cheapest_share >= 6 ? `${s.store_name} ${pctPlain(s.cheapest_share, 1)}` : ""}
                  </span>
                ))}
            </div>
            <div className="shops">
              {shops.map((s, i) => (
                <div key={s.store} className="shop rise" style={{ ...fieldStyle(s.store), ["--i" as string]: i } as React.CSSProperties}>
                  <div className="shop-n">
                    <span>{s.store_name}</span>
                  </div>
                  <div>
                    <div className="shop-v num">{pctPlain(s.cheapest_share, 1)}</div>
                    <div style={{ fontSize: 14, marginTop: 6 }}>{t.analytics.shopCheapest(int(s.cheapest_count))}</div>
                  </div>
                  <dl className="num">
                    <div>
                      <dt>{t.analytics.shopCurrent}</dt>
                      <dd>{int(s.current)}</dd>
                    </div>
                    <div>
                      <dt>{t.analytics.shopChanges7}</dt>
                      <dd>{int(s.changes_7d)}</dd>
                    </div>
                    <div>
                      <dt>{t.analytics.shopChanges30}</dt>
                      <dd>{int(s.changes_30d)}</dd>
                    </div>
                    <div>
                      <dt>{t.analytics.shopPromo}</dt>
                      <dd>{int(s.promo_listings)}</dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="sec" aria-labelledby="act-h">
        <Head kicker={t.analytics.moveKicker} title={t.analytics.moveH} text={t.analytics.moveP} id="act-h" />
        <div className="two">
          <div className="panel">
            <div className="panel-h">
              <b>{t.analytics.activityLabel}</b>
              <div className="legend">
                {actStores.map((k) => (
                  <span key={k} className="pill" style={fieldStyle(k)}>
                    <i style={{ background: shopOf(k).line }} />
                    {shopOf(k).label}
                  </span>
                ))}
              </div>
            </div>
            {activity.data ? (
              <ActivityBars days={actDays} points={activity.data} stores={actStores} upLabel={t.analytics.rises} downLabel={t.analytics.cuts} label={t.analytics.activityLabel} />
            ) : (
              <div className="skel" style={{ height: 240 }} />
            )}
            <p className="note">↑ {t.analytics.rises} · ↓ {t.analytics.cuts}</p>
          </div>
          <div className="panel">
            <div className="panel-h">
              <b>{t.analytics.distH}</b>
              <small>{t.analytics.distP}</small>
            </div>
            {dist.data ? (
              <Histogram
                bins={dist.data}
                height={240}
                label={t.analytics.distLabel}
                tip={(b) => t.analytics.distTip(pct(b.lower), pct(b.upper), t.common.changes(b.count))}
              />
            ) : (
              <div className="skel" style={{ height: 240 }} />
            )}
          </div>
        </div>
      </section>

      <section className="sec" aria-labelledby="mv-h">
        <Head kicker={t.analytics.moversKicker} title={t.analytics.moversH(range)} text={t.analytics.moversP} id="mv-h" />
        <div className="moves">
          <div>
            <h3>
              <span>{t.analytics.fell}</span>
              <span className="down">{t.analytics.largest}</span>
            </h3>
            <ol>{drops.data?.length ? drops.data.map((x) => <Move key={`${x.product_id}`} m={x} />) : <p className="muted">{drops.isLoading ? t.common.loading : t.analytics.none}</p>}</ol>
          </div>
          <div>
            <h3>
              <span>{t.analytics.rose}</span>
              <span className="up">{t.analytics.largest}</span>
            </h3>
            <ol>{rises.data?.length ? rises.data.map((x) => <Move key={`${x.product_id}`} m={x} />) : <p className="muted">{rises.isLoading ? t.common.loading : t.analytics.none}</p>}</ol>
          </div>
        </div>
      </section>

      <section className="sec" aria-labelledby="gap-h">
        <Head kicker={t.analytics.gapsKicker} title={t.analytics.gapsH} text={t.analytics.gapsP} id="gap-h" />
        <div className="panel scroll">
          <table className="db gaps">
            <thead>
              <tr>
                <th scope="col">{t.analytics.col.perfume}</th>
                <th scope="col">{t.analytics.col.cheapest}</th>
                <th scope="col">{t.analytics.col.dearest}</th>
                <th scope="col">{t.analytics.col.gap}</th>
              </tr>
            </thead>
            <tbody ref={peek}>
              {(gaps.data ?? []).map((g) => {
                const dear = g.card.offers.filter((o) => o.store === g.dearest_store).sort((a, b) => b.price - a.price)[0];
                const maxGap = Math.max(...(gaps.data ?? []).map((x) => x.gap_percent));
                return (
                  <tr key={g.card.key} className="link" data-img={g.card.image_url ?? undefined} data-field={shopOf(g.card.cheapest_store).field} onClick={() => (window.location.href = `/product/${g.card.product_id}`)}>
                    <td className="nmc">
                      <Link className="nm" to={`/product/${g.card.product_id}`}>
                        {g.card.brand} {g.card.name}
                      </Link>
                      <small className="muted num" style={{ display: "block", fontSize: 13.5 }}>
                        {spec(g.card)}
                      </small>
                    </td>
                    <td className="num">
                      <span className="pill" style={fieldStyle(g.card.cheapest_store)}>
                        {shopOf(g.card.cheapest_store).label}
                      </span>
                      {eur(g.card.min_price)}
                    </td>
                    <td className="num">
                      <span className="pill">{shopOf(g.dearest_store).label}</span>
                      {eur(dear?.price ?? g.card.max_price)}
                    </td>
                    <td className="num">
                      <span className="gapbar" aria-hidden="true">
                        <span style={{ width: `${(g.gap_percent / maxGap) * 100}%` }} />
                      </span>
                      <b style={{ fontWeight: 500 }}>{pctPlain(g.gap_percent)}</b> <span className="muted">· {eur(g.gap_eur)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="sec" aria-labelledby="heat-h">
        <Head kicker={t.analytics.heatKicker} title={t.analytics.heatH} text={t.analytics.heatP} id="heat-h" />
        <div className="panel">
          {heat.data ? (
            <div className="scroll">
              <table className="heat">
                <thead>
                  <tr>
                    <th scope="col">
                      <span className="sr">{t.catalog.col.brand}</span>
                    </th>
                    {heat.data.stores.map((s) => (
                      <th key={s} scope="col">
                        <span className="pill" style={fieldStyle(s)}>
                          {shopOf(s).label}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {heat.data.brands.map((b) => (
                    <tr key={b}>
                      <th scope="row" className="b">
                        {b}
                      </th>
                      {heat.data!.stores.map((s) => {
                        const c = heat.data!.cells.find((x) => x.brand === b && x.store === s);
                        if (!c) return <td key={s} className="na">—</td>;
                        const a = Math.min(1, c.premium / heatMax);
                        const style = {
                          ["--cell" as string]: `rgba(208, 16, 111, ${0.06 + a * 0.8})`,
                          ["--cell-ink" as string]: a > 0.5 ? "#fff" : "var(--ink)",
                        } as React.CSSProperties;
                        return (
                          <td key={s} style={style} title={t.analytics.heatTip(pct(c.premium, 1), t.common.bottles(c.bottles))}>
                            <span className="num">{c.premium < 0.5 ? "0%" : pct(c.premium)}</span>
                            <small className="num">{int(c.bottles)}</small>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="skel" style={{ height: 420 }} />
          )}
          <div className="ramp" aria-hidden="true">
            <span>
              <i style={{ ["--cell" as string]: "rgba(208,16,111,.06)" } as React.CSSProperties} />
              {t.analytics.heatLow} · 0%
            </span>
            {[0.25, 0.5, 0.75].map((a) => (
              <span key={a}>
                <i style={{ ["--cell" as string]: `rgba(208,16,111,${0.06 + a * 0.8})` } as React.CSSProperties} />
                {pct(heatMax * a)}
              </span>
            ))}
            <span>
              <i style={{ ["--cell" as string]: "rgba(208,16,111,.86)" } as React.CSSProperties} />
              {t.analytics.heatHigh} · {pct(heatMax)}
            </span>
          </div>
        </div>
      </section>

      <section className="sec" aria-labelledby="bands-h">
        <Head kicker={t.analytics.bandsKicker} title={t.analytics.bandsH} text={t.analytics.bandsP} id="bands-h" />
        <div className="panel bands">
          {bandsBy.map(([store, counts]) => {
            const total = counts.reduce((a, b) => a + b, 0) || 1;
            return (
              <div key={store} className="band-row">
                <b>{shopOf(store).label}</b>
                <div className="band-bar" role="img" aria-label={`${shopOf(store).label}: ${counts.map((c, i) => `${bandLabel(i)} ${pctPlain((c / total) * 100)}`).join(", ")}`}>
                  {counts.map((c, i) =>
                    c ? (
                      <span
                        key={i}
                        title={`${bandLabel(i)}: ${t.analytics.listings(c)} (${pctPlain((c / total) * 100)})`}
                        style={{ flexGrow: c, flexBasis: 0, ["--line" as string]: shopOf(store).line, ["--o" as string]: 0.25 + (i / (BAND_EDGES.length - 1)) * 0.75 } as React.CSSProperties}
                      />
                    ) : null,
                  )}
                </div>
                <span className="num muted" style={{ textAlign: "right" }}>
                  {int(total)}
                </span>
              </div>
            );
          })}
          <div className="band-key">
            {BAND_EDGES.map((_, i) => (
              <span key={i}>
                <i style={{ ["--o" as string]: 0.25 + (i / (BAND_EDGES.length - 1)) * 0.75 } as React.CSSProperties} />
                {bandLabel(i)}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export default function Analytics() {
  const t = useT();
  const { user } = useAuth();
  return (
    <AppShell>
      {hasPro(user) ? (
        <ProAnalytics />
      ) : (
        <div className="pg-an">
          <section className="phead">
            <div>
              <h1>{t.analytics.title}</h1>
              <p className="sub">{t.analytics.freeSub}</p>
            </div>
          </section>
          <ProGate />
        </div>
      )}
    </AppShell>
  );
}
