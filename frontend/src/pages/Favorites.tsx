import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff } from "lucide-react";
import { toast } from "sonner";
import { api, type FavoriteItem } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { usePageContext } from "@/contexts/ChatContext";
import { useFavorites } from "@/contexts/FavoritesContext";
import { useT } from "@/i18n";
import { exportUrl } from "@/lib/download";
import { day, eur0, eur, int, pct } from "@/lib/format";
import { fieldStyle, shopOf } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";
import ExportMenu from "@/components/mp/ExportMenu";
import Img from "@/components/mp/Img";
import { spec } from "@/components/mp/SearchBox";
import { Ribbon, Sparkline } from "@/components/mp/charts";

type Sort = "added" | "price" | "drop";

function bestOf(f: FavoriteItem) {
  return f.offers.find((o) => o.is_available) ?? f.offers[0] ?? null;
}

function cheapestLine(f: FavoriteItem): (number | null)[] {
  if (!f.series) return [];
  const lines = Object.values(f.series.shops);
  return f.series.days.map((_, i) => {
    const v = lines.map((l) => l[i]).filter((x): x is number => x != null);
    return v.length ? Math.min(...v) : null;
  });
}

function Row({ f, defTh, onRemove }: { f: FavoriteItem; defTh: number; onRemove: (f: FavoriteItem) => void }) {
  const t = useT();
  const qc = useQueryClient();
  const [gone, setGone] = useState(false);
  const best = bestOf(f);
  const live = f.offers.filter((o) => o.is_available);
  const c = f.change_30d;
  const name = f.display_name || f.title;

  async function patch(body: { alert_enabled?: boolean; alert_threshold_percent?: number }) {
    try {
      await api.updateFavorite(f.product_id, body);
      qc.invalidateQueries({ queryKey: ["favorites"] });
    } catch {
      toast.error(t.common.error);
    }
  }

  return (
    <li className={`fav ${gone ? "gone" : ""}`}>
      <Link className="f-pic" to={`/product/${f.product_id}`} style={fieldStyle(best?.store ?? f.store_name)} aria-label={`${f.brand} ${name}`}>
        <Img src={f.image_url} brand={f.brand ?? ""} />
      </Link>
      <div className="f-info">
        <span className="f-brand">{f.brand}</span>
        <Link className="f-name" to={`/product/${f.product_id}`}>
          {name}
        </Link>
        <span className="f-spec">{spec(f)}</span>
        <div className="f-alert">
          <span>{t.favorites.tellAt}</span>
          <select
            aria-label={t.favorites.thLabel}
            value={f.alert_threshold_percent == null ? "" : String(f.alert_threshold_percent)}
            onChange={(e) => patch({ alert_threshold_percent: Number(e.target.value || 0) })}
          >
            <option value="">{t.favorites.def(`−${defTh}%`)}</option>
            {[5, 10, 15, 20, 30].map((v) => (
              <option key={v} value={v}>
                −{v}%
              </option>
            ))}
          </select>
          <button className="bell" type="button" aria-pressed={f.alert_enabled} aria-label={f.alert_enabled ? t.favorites.bellOn : t.favorites.bellOff} onClick={() => patch({ alert_enabled: !f.alert_enabled })}>
            {f.alert_enabled ? <Bell /> : <BellOff />}
            {f.alert_enabled ? t.favorites.on : t.favorites.off}
          </button>
          <button
            className="rm"
            type="button"
            onClick={() => {
              setGone(true);
              setTimeout(() => onRemove(f), matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 280);
            }}
          >
            {t.favorites.remove}
          </button>
        </div>
      </div>
      <div className="f-shops">
        {f.offers.map((o, i) => (
          <div key={o.product_id} className={`f-shop ${i === 0 && o.is_available ? "best" : ""} ${o.is_available ? "" : "out"}`}>
            <span>
              <span className="pill" style={i === 0 && o.is_available ? fieldStyle(o.store) : undefined}>
                {shopOf(o.store).label}
              </span>
            </span>
            <span className="num">{o.is_available ? eur(o.price) : t.common.outOfStock}</span>
          </div>
        ))}
        {!live.length && <span className="muted">{t.favorites.outEverywhere}</span>}
      </div>
      <div className="f-price">
        <div className="v num">{eur(best?.price ?? f.current_price)}</div>
        <div className={`c num ${c == null || Math.abs(c) < 0.5 ? "muted" : c < 0 ? "down" : "up"}`}>
          {c == null ? t.favorites.newMonth : Math.abs(c) < 0.5 ? t.favorites.same : t.favorites.in30(pct(c, 1))}
        </div>
        {f.series && (
          <div className="f-trend">
            <Sparkline values={cheapestLine(f)} />
            <Ribbon cheapest={f.series.cheapest} label={t.favorites.cheapestEach} />
            <small>
              <span>{t.favorites.ago30}</span>
              <span>{t.favorites.cheapestEach}</span>
            </small>
          </div>
        )}
      </div>
    </li>
  );
}

export default function Favorites() {
  const t = useT();
  const { user } = useAuth();
  const { toggleFavorite } = useFavorites();
  const qc = useQueryClient();
  const [sort, setSort] = useState<Sort>("added");
  const { data, isLoading } = useQuery({ queryKey: ["favorites"], queryFn: api.listFavorites });
  const list = useMemo(() => data ?? [], [data]);
  usePageContext(`Favorites list with ${list.length} bottles: ${list.slice(0, 8).map((f) => `${f.brand} ${f.display_name ?? f.title} ${f.volume ?? ""}`).join("; ")}`);

  const prefs = user?.preferences;
  const defTh = prefs?.notification_threshold_percent ?? 5;
  const tgOn = !!prefs?.telegram_chat_id && (prefs?.notification_channels ?? []).includes("telegram");
  const mailOn = (prefs?.notification_channels ?? []).includes("email");

  const sorted = useMemo(() => {
    const l = list.slice();
    if (sort === "price") l.sort((a, b) => (bestOf(a)?.price ?? a.current_price) - (bestOf(b)?.price ?? b.current_price));
    if (sort === "drop") l.sort((a, b) => (a.change_30d ?? 99) - (b.change_30d ?? 99));
    return l;
  }, [list, sort]);

  const fell = list.filter((f) => f.change_30d != null && f.change_30d < -0.5).length;
  const saved = list.reduce((s, f) => {
    const live = f.offers.filter((o) => o.is_available).map((o) => o.price);
    return s + (live.length > 1 ? Math.max(...live) - Math.min(...live) : 0);
  }, 0);
  const alertsOn = list.filter((f) => f.alert_enabled).length;
  const asOf = list[0]?.series?.days.slice(-1)[0];

  async function remove(f: FavoriteItem) {
    await toggleFavorite(f.product_id);
    toast(t.favorites.removed(`${f.brand ?? ""} ${f.display_name ?? f.title}`.trim()), {
      action: {
        label: t.common.undo,
        onClick: async () => {
          await toggleFavorite(f.product_id);
          if (f.alert_threshold_percent || !f.alert_enabled)
            await api.updateFavorite(f.product_id, { alert_threshold_percent: f.alert_threshold_percent ?? undefined, alert_enabled: f.alert_enabled });
          qc.invalidateQueries({ queryKey: ["favorites"] });
        },
      },
    });
  }

  return (
    <AppShell>
      <div className="pg-fav">
        <section className="phead">
          <div>
            <h1>{t.favorites.title}</h1>
            <p className="sub num">{t.favorites.sub(list.length, asOf ? day(asOf) : "—")}</p>
          </div>
        </section>

        <section className="sum" aria-label={t.favorites.title}>
          <div className="s-tile rise">
            <span className="l">{t.favorites.sFell}</span>
            <div>
              <div className="v num">{int(fell)}</div>
              <div className="n">{t.favorites.sFellN(list.length)}</div>
            </div>
          </div>
          <div className="s-tile rise" style={{ ["--i" as string]: 1 } as React.CSSProperties}>
            <span className="l">{t.favorites.sSave}</span>
            <div>
              <div className="v num">{eur0(saved)}</div>
              <div className="n">{t.favorites.sSaveN}</div>
            </div>
          </div>
          <div className="s-tile rise" style={{ ["--i" as string]: 2 } as React.CSSProperties}>
            <span className="l">{t.favorites.sOn}</span>
            <div>
              <div className="v num">{int(alertsOn)}</div>
              <div className="n">{t.favorites.sOnN}</div>
            </div>
          </div>
          <div className="s-tile chan rise" style={{ ["--i" as string]: 3 } as React.CSSProperties}>
            <span className="l">{t.favorites.chan}</span>
            <div className="chan-rows">
              <div className="chan-row">
                <span>Telegram</span>
                {tgOn ? (
                  <span className="pill" style={{ ["--field" as string]: "var(--f-220)" } as React.CSSProperties}>
                    <i />
                    {t.favorites.connected}
                  </span>
                ) : (
                  <span className="pill off">{t.favorites.off}</span>
                )}
              </div>
              <div className="chan-row">
                <span>Email</span>
                {mailOn ? (
                  <span className="pill" style={{ ["--field" as string]: "var(--f-220)" } as React.CSSProperties}>
                    <i />
                    {t.favorites.on}
                  </span>
                ) : (
                  <span className="pill off">{t.favorites.off}</span>
                )}
              </div>
              <div className="chan-row">
                <span className="n">{t.favorites.chanNote}</span>
                <Link to="/profile#alerts">{t.favorites.change}</Link>
              </div>
            </div>
          </div>
        </section>

        <div className="bar">
          <h2 id="list-h">{t.favorites.listH}</h2>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <div className="seg" role="group" aria-label={t.favorites.sort}>
              {(
                [
                  ["added", t.favorites.sAdded],
                  ["price", t.favorites.sPrice],
                  ["drop", t.favorites.sDrop],
                ] as [Sort, string][]
              ).map(([k, l]) => (
                <button key={k} type="button" aria-pressed={sort === k} onClick={() => setSort(k)}>
                  {l}
                </button>
              ))}
            </div>
            {list.length > 0 && (
              <ExportMenu
                path={(fmt) => exportUrl("/exports/catalog", { format: fmt, view: "listings", ids: list.flatMap((f) => (f.offers.length ? f.offers.map((o) => o.product_id) : [f.product_id])) })}
                fallbackName="marketpulse_favorites"
              />
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="list">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skel" style={{ height: 200 }} />
            ))}
          </div>
        ) : sorted.length ? (
          <ol className="list" aria-labelledby="list-h">
            {sorted.map((f) => (
              <Row key={f.id} f={f} defTh={defTh} onRemove={remove} />
            ))}
          </ol>
        ) : (
          <div className="empty">
            <h3>{t.favorites.emptyH}</h3>
            <p>{t.favorites.emptyP}</p>
            <Link className="btn btn-ink" to="/catalog">
              {t.favorites.toCatalog}
            </Link>
          </div>
        )}
      </div>
    </AppShell>
  );
}
