import { Fragment, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, type AdminHealthResponse, type AdminScrapingRule, type AdminSiteHealth, type AdminUserRead } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { usePageContext } from "@/contexts/ChatContext";
import { useT } from "@/i18n";
import { ago, dateTime, day, int, num } from "@/lib/format";
import { fieldStyle, isShownShop, shopOf } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";

type Tab = "health" | "scraping" | "quality" | "users";
const TABS: Tab[] = ["health", "scraping", "quality", "users"];
const LIMITS: (number | null)[] = [50, 100, 500, 1000, null];
const STUCK_MS = 6 * 60 * 1000;

const healthQuery = {
  queryKey: ["admin", "health"],
  queryFn: () => api.admin.health().then((h) => ({ ...h, sites: h.sites.filter((s) => isShownShop(s.domain)) })),
};

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message.replace(/^API Error:\s*/, "") : String(e);
}

function Domain({ s }: { s: AdminSiteHealth }) {
  const shop = shopOf(s.domain);
  return (
    <td className="dom">
      <b>{s.domain}</b>
      <small>
        <span className="pill" style={{ ...fieldStyle(s.domain), height: 20, fontSize: 12 }}>
          {shop.label}
        </span>
      </small>
    </td>
  );
}

function Loading() {
  const t = useT();
  return (
    <div className="skel" style={{ height: 240 }} role="status" aria-label={t.common.loading} />
  );
}

function Failed({ retry }: { retry: () => void }) {
  const t = useT();
  return (
    <div className="empty">
      <p>{t.common.errorLoad}</p>
      <button className="btn btn-soft btn-sm" type="button" onClick={retry}>
        {t.common.retry}
      </button>
    </div>
  );
}

// ── Health ──────────────────────────────────────────────────────────────────

function Worker() {
  const t = useT();
  const { data: w } = useQuery({ queryKey: ["admin", "worker"], queryFn: api.admin.workerStatus, refetchInterval: 5000 });
  return (
    <div className="card worker">
      <span className={`dot ${w?.online ? "live" : "off"}`} aria-hidden="true" />
      <b>{t.admin.worker}</b>
      <span>{w?.online ? t.admin.online : t.admin.offline}</span>
      {w?.last_seen_ago_s != null && <span className="muted">{t.admin.seen(ago(new Date(Date.now() - w.last_seen_ago_s * 1000)))}</span>}
      <span className="muted" style={{ marginLeft: "auto" }}>
        {t.admin.queue} <b style={{ color: "var(--ink)" }}>{int(w?.queue_depth ?? 0)}</b> · {t.admin.nightly}
      </span>
    </div>
  );
}

function HealthTab({ data }: { data: AdminHealthResponse }) {
  const t = useT();
  const running = data.sites.filter((s) => s.product_count > 0).length;
  const kpis = [
    { l: t.admin.kProducts, v: int(data.total_products) },
    { l: t.admin.kUsers, v: int(data.total_users) },
    { l: t.admin.kSites, v: int(data.sites.length), n: t.admin.kSitesN(running) },
    { l: t.admin.kLatency, v: t.admin.ms(Math.round(data.db_latency_ms)) },
  ];
  const errors = data.sites.filter((s) => s.last_error);
  return (
    <section className="panel" role="tabpanel" aria-label={t.admin.tabs.health}>
      <div className="kpis">
        {kpis.map((k, i) => (
          <div key={k.l} className="kpi rise" style={{ ["--i" as string]: i } as React.CSSProperties}>
            <span className="l">{k.l}</span>
            <span>
              <span className="v num">{k.v}</span>
              <div className="n">{k.n ?? "\u00a0"}</div>
            </span>
          </div>
        ))}
      </div>
      <Worker />
      <div className="card">
        <h2>{t.admin.sites}</h2>
        {data.sites.length ? (
          <div className="scroll">
            <table className="adm">
              <thead>
                <tr>
                  <th scope="col">{t.admin.cDomain}</th>
                  <th scope="col" className="r">
                    {t.admin.cProducts}
                  </th>
                  <th scope="col">{t.admin.cHealth}</th>
                  <th scope="col" className="r">
                    {t.admin.cOk}
                  </th>
                  <th scope="col" className="r">
                    {t.admin.cFail}
                  </th>
                  <th scope="col" className="r">
                    {t.admin.cLast}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.sites.map((s) => {
                  const h = Math.max(0, Math.min(1, s.health_score));
                  const col = h > 0.7 ? "var(--ok)" : h > 0.4 ? "var(--warn)" : "var(--bad)";
                  return (
                    <tr key={s.domain}>
                      <Domain s={s} />
                      <td className="r num">{int(s.product_count)}</td>
                      <td>
                        <div className="health" style={{ ["--h" as string]: col } as React.CSSProperties}>
                          <div className="t">
                            <span style={{ width: `${h * 100}%` }} />
                          </div>
                          <small className="num">{Math.round(h * 100)}%</small>
                        </div>
                      </td>
                      <td className="r num ok">{int(s.success_count)}</td>
                      <td className="r num bad">{int(s.failure_count)}</td>
                      <td className="r muted">{dateTime(s.last_scrape_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">{t.admin.noSites}</p>
        )}
      </div>
      {errors.length > 0 && (
        <div className="errs" role="region" aria-label={t.admin.errors}>
          <h2>{t.admin.errors}</h2>
          {errors.map((s) => (
            <p key={s.domain}>
              <span>{s.domain}</span>
              <span>{s.last_error}</span>
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

// ── Scraping ────────────────────────────────────────────────────────────────

function limitLabel(l: number | null, unlimited: string) {
  return l == null ? unlimited : String(l);
}

function LimitSelect({ value, onChange, label, disabled }: { value: number | null; onChange: (v: number | null) => void; label: string; disabled?: boolean }) {
  const t = useT();
  return (
    <select className="sel" aria-label={label} value={value == null ? "" : String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      {LIMITS.map((l) => (
        <option key={String(l)} value={l == null ? "" : String(l)}>
          {limitLabel(l, t.admin.unlimited)}
        </option>
      ))}
    </select>
  );
}

function Rules({ domain }: { domain: string | null }) {
  const t = useT();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "rules", domain],
    queryFn: () => api.admin.rules(domain!),
    enabled: !!domain,
    retry: false,
  });
  const shown = data
    ? Object.fromEntries(
        (Object.entries(data) as [keyof AdminScrapingRule, unknown][]).filter(([k, v]) => v != null && (String(k).endsWith("_css") || k === "site_name")),
      )
    : null;
  return (
    <div className="card">
      <h2>{domain ? t.admin.rulesFor(domain) : t.admin.rules}</h2>
      {!domain ? (
        <p className="muted">{t.admin.rulesPick}</p>
      ) : isLoading ? (
        <div className="skel" style={{ height: 160 }} />
      ) : isError || !shown ? (
        <p className="muted">{t.admin.noRules(domain)}</p>
      ) : (
        <pre className="code">{JSON.stringify(shown, null, 2)}</pre>
      )}
    </div>
  );
}

function Log() {
  const t = useT();
  const [live, setLive] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const { data } = useQuery({ queryKey: ["admin", "logs"], queryFn: () => api.admin.logs(100), refetchInterval: live ? 2000 : false });
  const lines = data?.lines ?? [];
  useEffect(() => {
    const el = box.current;
    if (el && live) el.scrollTop = el.scrollHeight;
  }, [lines.length, live]);
  return (
    <div className="card">
      <h2>
        <span>
          {t.admin.log} <small className="muted num">{data ? t.admin.logOf(lines.length, data.total) : ""}</small>
        </span>
        <button className="btn btn-line btn-sm" type="button" aria-pressed={live} onClick={() => setLive((v) => !v)}>
          {live ? t.admin.live : t.admin.pausedLog}
        </button>
      </h2>
      <div className="log" ref={box} aria-live="off">
        {lines.length ? (
          lines.map((l, i) => {
            const k = /\b(ERROR|CRITICAL)\b/.test(l) ? "e" : /\bWARN(ING)?\b/.test(l) ? "w" : "";
            return (
              <div key={i} className={k}>
                {l}
              </div>
            );
          })
        ) : (
          <div className="muted">{t.admin.noLog}</div>
        )}
      </div>
    </div>
  );
}

function ScrapingTab({ data }: { data: AdminHealthResponse }) {
  const t = useT();
  const qc = useQueryClient();
  // Domain -> last_scrape_at when the run was queued; a new value means it finished.
  const [running, setRunning] = useState<Record<string, { snap: string | null; at: number }>>({});
  const [limits, setLimits] = useState<Record<string, number | null>>({});
  const [master, setMaster] = useState<number | null>(100);
  const [ask, setAsk] = useState(false);
  const [busyAll, setBusyAll] = useState(false);
  const [regen, setRegen] = useState<string | null>(null);
  const [rulesFor, setRulesFor] = useState<string | null>(null);

  const liveSites = data.sites.filter((s) => shopOf(s.domain).live);
  const limitOf = (d: string) => (d in limits ? limits[d] : 100);

  useEffect(() => {
    if (!Object.keys(running).length) return;
    const id = setInterval(async () => {
      const fresh = await api.admin.health().catch(() => null);
      if (fresh) qc.setQueryData(healthQuery.queryKey, fresh);
      setRunning((prev) => {
        const next = { ...prev };
        for (const [d, r] of Object.entries(prev)) {
          const now = fresh?.sites.find((s) => s.domain === d)?.last_scrape_at ?? null;
          if (fresh && now !== r.snap) {
            toast.success(t.admin.finished(d));
            delete next[d];
          } else if (Date.now() - r.at > STUCK_MS) {
            toast.error(t.admin.stuck(d));
            delete next[d];
          }
        }
        return next;
      });
    }, 8000);
    return () => clearInterval(id);
  }, [running, qc, t]);

  function mark(domains: string[]) {
    const at = Date.now();
    setRunning((prev) => {
      const next = { ...prev };
      for (const d of domains) next[d] = { snap: data.sites.find((s) => s.domain === d)?.last_scrape_at ?? null, at };
      return next;
    });
  }

  async function runOne(d: string) {
    const lim = limitOf(d);
    try {
      await api.admin.triggerScrape(d, lim);
      mark([d]);
      toast.success(t.admin.queued(d, limitLabel(lim, t.admin.unlimited)));
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function runAll() {
    setAsk(false);
    setBusyAll(true);
    try {
      const res = await Promise.allSettled(liveSites.map((s) => api.admin.triggerScrape(s.domain, master)));
      const ok = liveSites.filter((_, i) => res[i].status === "fulfilled").map((s) => s.domain);
      mark(ok);
      const failed = res.flatMap((r, i) => (r.status === "rejected" ? [`${liveSites[i].domain}: ${errMsg(r.reason)}`] : []));
      if (failed.length) toast.error(`${t.admin.queuedAll(ok.length, res.length)}\n${failed.join("\n")}`, { duration: 8000 });
      else toast.success(t.admin.queuedAll(ok.length, res.length));
    } finally {
      setBusyAll(false);
    }
  }

  async function regenerate(d: string) {
    setRegen(d);
    try {
      await api.admin.regenerateRules(d);
      toast.success(t.admin.regenAsked(d));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setRegen(null);
    }
  }

  const stuck = Object.keys(running).length;
  return (
    <section className="panel" role="tabpanel" aria-label={t.admin.tabs.scraping}>
      <div className="card runall">
        <div>
          <h2 style={{ marginBottom: 6 }}>{t.admin.runAllH}</h2>
          <p>{t.admin.runAllP}</p>
        </div>
        <div className="acts">
          <LimitSelect value={master} onChange={setMaster} label={t.admin.limitAll} />
          <button className="btn btn-ink btn-sm" type="button" onClick={() => setAsk(true)} disabled={busyAll || !liveSites.length}>
            {busyAll ? t.admin.queueing : t.admin.runAll(liveSites.length)}
          </button>
          {stuck > 0 && (
            <button
              className="btn btn-line btn-sm"
              type="button"
              onClick={() => {
                setRunning({});
                toast.success(t.admin.resetDone);
              }}
            >
              {t.admin.reset(stuck)}
            </button>
          )}
        </div>
        {ask && (
          <div className="cbox fade" role="alertdialog" aria-labelledby="runall-q" style={{ gridColumn: "1 / -1" }}>
            <span id="runall-q">{t.admin.runAllAsk(liveSites.length, limitLabel(master, t.admin.unlimited))}</span>
            <span className="acts">
              <button className="btn btn-ink btn-sm" type="button" onClick={runAll}>
                {t.common.yes}
              </button>
              <button className="btn btn-line btn-sm" type="button" onClick={() => setAsk(false)}>
                {t.common.cancel}
              </button>
            </span>
          </div>
        )}
      </div>
      <div className="card">
        <h2>{t.admin.perSite}</h2>
        <div className="scroll">
          <table className="adm">
            <thead>
              <tr>
                <th scope="col">{t.admin.cDomain}</th>
                <th scope="col">{t.admin.cHow}</th>
                <th scope="col" className="r">
                  {t.admin.cActions}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.sites.map((s) => {
                const paused = !shopOf(s.domain).live;
                const busy = s.domain in running;
                const how = t.admin.how[s.domain] ?? "";
                return (
                  <tr key={s.domain}>
                    <Domain s={s} />
                    <td>{paused ? <span className="cf">{t.admin.paused}</span> : <span className="muted">{how}</span>}</td>
                    <td className="r">
                      <div className="acts">
                        <button className="btn btn-line btn-sm" type="button" aria-pressed={rulesFor === s.domain} onClick={() => setRulesFor(s.domain)}>
                          {t.admin.rules}
                        </button>
                        <button className="btn btn-line btn-sm" type="button" disabled={regen === s.domain} onClick={() => regenerate(s.domain)}>
                          {regen === s.domain ? <span className="spin" aria-hidden="true" /> : null}
                          {t.admin.regen}
                        </button>
                        <LimitSelect
                          value={limitOf(s.domain)}
                          onChange={(v) => setLimits((p) => ({ ...p, [s.domain]: v }))}
                          label={t.admin.limitFor(s.domain)}
                          disabled={busy}
                        />
                        <button className="btn btn-ink btn-sm" type="button" disabled={busy || paused} onClick={() => runOne(s.domain)}>
                          {busy ? (
                            <>
                              <span className="spin" aria-hidden="true" /> {t.admin.running}
                            </>
                          ) : (
                            t.admin.run
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <div className="two">
        <Rules domain={rulesFor} />
        <Log />
      </div>
    </section>
  );
}

// ── Data quality ────────────────────────────────────────────────────────────

function QualityTab() {
  const t = useT();
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["admin", "quality"], queryFn: api.admin.dataQuality });
  if (isLoading) return <Loading />;
  if (isError || !data) return <Failed retry={() => refetch()} />;
  const total = Math.max(data.total_products, 1);
  const share = (n: number) => t.admin.ofCatalog(`${num((n / total) * 100, 1)}%`);
  const rows = [
    { l: t.admin.qProducts, v: data.total_products, n: t.admin.qProductsN, tone: "var(--ok)" },
    { l: t.admin.qEvents, v: data.total_price_events, n: t.admin.qEventsN, tone: "var(--ok)" },
    { l: t.admin.qImg, v: data.products_without_image, n: data.products_without_image ? share(data.products_without_image) : t.admin.allGood },
    { l: t.admin.qHist, v: data.products_without_history, n: data.products_without_history ? share(data.products_without_history) : t.admin.allGood },
    { l: t.admin.qUngrouped, v: data.products_ungrouped, n: data.products_ungrouped ? share(data.products_ungrouped) : t.admin.allGood },
  ];
  return (
    <section className="panel" role="tabpanel" aria-label={t.admin.tabs.quality}>
      <div className="card">
        <h2>{t.admin.qH}</h2>
        {rows.map((r) => (
          <div key={r.l} className="q" style={{ ["--tone" as string]: r.tone ?? (r.v ? "var(--warn)" : "var(--ok)") } as React.CSSProperties}>
            <i aria-hidden="true" />
            <span>
              <b>{r.l}</b>
              <small>{r.n}</small>
            </span>
            <span className="v num">{int(r.v)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Users ───────────────────────────────────────────────────────────────────

function UsersTab() {
  const t = useT();
  const qc = useQueryClient();
  const { user: me, refreshUser } = useAuth();
  const { data: users, isLoading, isError, refetch } = useQuery({ queryKey: ["admin", "users"], queryFn: api.admin.users });
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState<number | null>(null);
  const [confirmDel, setConfirmDel] = useState<number | null>(null);
  const [askBatch, setAskBatch] = useState(false);

  if (isLoading) return <Loading />;
  if (isError || !users) return <Failed retry={() => refetch()} />;

  const put = (u: AdminUserRead) => qc.setQueryData<AdminUserRead[]>(["admin", "users"], (prev) => prev?.map((x) => (x.id === u.id ? u : x)));
  const selectable = users.filter((u) => !u.is_admin).map((u) => u.id);
  const allOn = selectable.length > 0 && selectable.every((id) => sel.has(id));

  async function patch(u: AdminUserRead, body: { is_active?: boolean; plan?: "free" | "pro" }, done: (x: AdminUserRead) => string) {
    setBusy(u.id);
    try {
      const x = await api.admin.updateUser(u.id, body);
      put(x);
      if (me?.id === x.id) refreshUser().catch(() => undefined);
      toast.success(done(x));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function remove(u: AdminUserRead) {
    setBusy(u.id);
    try {
      await api.admin.deleteUser(u.id);
      qc.setQueryData<AdminUserRead[]>(["admin", "users"], (prev) => prev?.filter((x) => x.id !== u.id));
      setSel((p) => {
        const n = new Set(p);
        n.delete(u.id);
        return n;
      });
      setConfirmDel(null);
      toast.success(t.admin.deleted(u.email));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function batchOff() {
    setAskBatch(false);
    try {
      const r = await api.admin.batchDeactivate([...sel]);
      toast.success(t.admin.deactivated(r.updated));
      setSel(new Set());
      refetch();
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  return (
    <section className="panel" role="tabpanel" aria-label={t.admin.tabs.users}>
      <div className="card">
        <h2>
          <span>{t.admin.usersH}</span>
          <small className="muted" style={{ fontWeight: 400, fontSize: 14 }}>
            {t.admin.planHint}
          </small>
        </h2>
        {sel.size > 0 && (
          <div className="batch fade">
            <span>{askBatch ? t.admin.deactivateAsk(sel.size) : t.admin.selected(sel.size)}</span>
            <span className="sp">
              {askBatch ? (
                <>
                  <button className="btn btn-red btn-sm" type="button" onClick={batchOff}>
                    {t.common.yes}
                  </button>
                  <button className="btn btn-line btn-sm" type="button" onClick={() => setAskBatch(false)}>
                    {t.common.cancel}
                  </button>
                </>
              ) : (
                <>
                  <button className="btn btn-line btn-sm" type="button" onClick={() => setAskBatch(true)}>
                    {t.admin.deactivateSel}
                  </button>
                  <button className="btn btn-line btn-sm" type="button" onClick={() => setSel(new Set())}>
                    {t.common.clear}
                  </button>
                </>
              )}
            </span>
          </div>
        )}
        {users.length ? (
          <div className="scroll">
            <table className="adm">
              <thead>
                <tr>
                  <th scope="col">
                    <input type="checkbox" aria-label={t.admin.selectAll} checked={allOn} onChange={() => setSel(allOn ? new Set() : new Set(selectable))} />
                  </th>
                  <th scope="col">{t.admin.cUser}</th>
                  <th scope="col">{t.admin.cJoined}</th>
                  <th scope="col">{t.admin.cPlan}</th>
                  <th scope="col" className="r">
                    {t.admin.cFavs}
                  </th>
                  <th scope="col">{t.admin.cStatus}</th>
                  <th scope="col" className="r">
                    <span className="sr">{t.admin.cActions}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const pro = u.plan === "pro";
                  return (
                    <Fragment key={u.id}>
                      <tr>
                        <td>
                          <input
                            type="checkbox"
                            aria-label={t.admin.selectOne(u.email)}
                            disabled={u.is_admin}
                            checked={sel.has(u.id)}
                            onChange={() =>
                              setSel((p) => {
                                const n = new Set(p);
                                if (n.has(u.id)) n.delete(u.id);
                                else n.add(u.id);
                                return n;
                              })
                            }
                          />
                        </td>
                        <td className="u">
                          <b>{u.email}</b>
                          <small>
                            {u.full_name || "—"}
                            {u.is_admin && <span className="badge b-adm">{t.admin.admin}</span>}
                          </small>
                        </td>
                        <td className="muted">{day(u.created_at)}</td>
                        <td>
                          <button
                            className={`badge ${pro ? "b-pro" : "b-free"}`}
                            type="button"
                            disabled={busy === u.id}
                            aria-label={pro ? t.admin.setFree(u.email) : t.admin.setPro(u.email)}
                            title={pro ? t.admin.setFree(u.email) : t.admin.setPro(u.email)}
                            onClick={() => patch(u, { plan: pro ? "free" : "pro" }, (x) => (x.plan === "pro" ? t.admin.nowPro(x.email) : t.admin.nowFree(x.email)))}
                          >
                            {pro ? "Pro" : t.common.free}
                          </button>
                        </td>
                        <td className="r num">{int(u.favorites_count)}</td>
                        <td>
                          <span className={`badge ${u.is_active ? "b-on" : "b-off"}`}>{u.is_active ? t.admin.active : t.admin.disabled}</span>
                        </td>
                        <td className="r">
                          <div className="acts">
                            <button
                              className="btn btn-line btn-sm"
                              type="button"
                              disabled={u.is_admin || busy === u.id}
                              onClick={() => patch(u, { is_active: !u.is_active }, (x) => (x.is_active ? t.admin.isOn(x.email) : t.admin.isOff(x.email)))}
                            >
                              {u.is_active ? t.admin.deactivate : t.admin.reactivate}
                            </button>
                            <button className="del" type="button" disabled={u.is_admin} aria-label={t.admin.del(u.email)} onClick={() => setConfirmDel(u.id)}>
                              <Trash2 size={16} aria-hidden="true" />
                            </button>
                          </div>
                        </td>
                      </tr>
                      {confirmDel === u.id && (
                        <tr className="confirm">
                          <td />
                          <td colSpan={6}>
                            <div className="cbox fade" role="alertdialog" aria-label={t.admin.del(u.email)}>
                              <span>{t.admin.delAsk(u.email)}</span>
                              <span className="acts">
                                <button className="btn btn-red btn-sm" type="button" disabled={busy === u.id} onClick={() => remove(u)}>
                                  {t.admin.delYes}
                                </button>
                                <button className="btn btn-line btn-sm" type="button" onClick={() => setConfirmDel(null)}>
                                  {t.common.cancel}
                                </button>
                              </span>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">{t.admin.noUsers}</p>
        )}
      </div>
    </section>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminPanel() {
  const t = useT();
  const nav = useNavigate();
  const { hash } = useLocation();
  const tab: Tab = (TABS as string[]).includes(hash.slice(1)) ? (hash.slice(1) as Tab) : "health";
  const health = useQuery(healthQuery);
  const { data: users } = useQuery({ queryKey: ["admin", "users"], queryFn: api.admin.users });
  usePageContext(`Admin panel, ${tab} tab: scraper health, scraping runs, data quality and user accounts.`);

  return (
    <AppShell>
      <div className="pg-admin">
        <section className="phead">
          <div>
            <h1>{t.admin.title}</h1>
            <p className="lead">{t.admin.lead}</p>
          </div>
        </section>
        <div className="seg atabs" role="tablist" aria-label={t.admin.tabsLabel}>
          {TABS.map((id) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} aria-pressed={tab === id} onClick={() => nav({ hash: id === "health" ? "" : id }, { replace: true })}>
              {t.admin.tabs[id]}
              {id === "users" && users && <span className="n num">{users.length}</span>}
            </button>
          ))}
        </div>
        {tab === "quality" ? (
          <QualityTab />
        ) : tab === "users" ? (
          <UsersTab />
        ) : health.isLoading ? (
          <Loading />
        ) : health.isError || !health.data ? (
          <Failed retry={() => health.refetch()} />
        ) : tab === "scraping" ? (
          <ScrapingTab data={health.data} />
        ) : (
          <HealthTab data={health.data} />
        )}
      </div>
    </AppShell>
  );
}
