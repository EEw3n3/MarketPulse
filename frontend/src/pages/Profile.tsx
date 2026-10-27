import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { usePageContext } from "@/contexts/ChatContext";
import { useT } from "@/i18n";
import { BRAND_OPTIONS } from "@/lib/brands";
import { dayLong, eur } from "@/lib/format";
import { PRO_PRICE, hasPro } from "@/lib/plan";
import { SHOPS, fieldStyle } from "@/lib/shops";
import AppShell from "@/components/mp/AppShell";
import LangSwitch from "@/components/mp/LangSwitch";

function Switch({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return <button className="sw" type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)} />;
}

/** Links a Telegram chat to this account. The bot binds whichever chat opens
 *  it, so the user sees which account is being linked before Telegram opens,
 *  and gets the /start command to paste when Telegram Web drops it. */
function TelegramConnect() {
  const t = useT();
  const { user, refreshUser } = useAuth();
  const [state, setState] = useState<"idle" | "ready" | "waiting" | "timeout">("idle");
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const connected = Boolean(user?.preferences?.telegram_chat_id);

  const stop = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };
  useEffect(() => stop, []);
  useEffect(() => {
    if (connected && (state === "waiting" || state === "ready")) {
      stop();
      setState("idle");
      toast.success(t.profile.tgConnected);
    }
  }, [connected, state, t]);

  async function start() {
    setBusy(true);
    try {
      const { deep_link } = await api.connectTelegram();
      setLink(deep_link);
      setState("ready");
    } catch {
      toast.error(t.profile.tgFail);
    } finally {
      setBusy(false);
    }
  }

  function poll() {
    stop();
    setState("waiting");
    let n = 0;
    timer.current = setInterval(() => {
      n += 1;
      refreshUser().catch(() => undefined);
      if (n >= 20) {
        stop();
        setState("timeout");
      }
    }, 3000);
  }

  const bot = link?.match(/t\.me\/([A-Za-z0-9_]+)/i)?.[1];
  const webUrl = bot ? `https://web.telegram.org/k/#@${bot}` : "https://web.telegram.org/k/";
  const token = link?.match(/[?&]start=([^&]+)/)?.[1];
  const command = token ? `/start ${token}` : null;

  async function copy() {
    if (!command) return;
    try {
      await navigator.clipboard.writeText(command);
      toast.success(t.profile.copied);
    } catch {
      toast.error(t.profile.copyFail);
    }
  }

  if (state === "idle")
    return (
      <button className="btn btn-soft btn-sm" type="button" onClick={start} disabled={busy}>
        {t.profile.connect}
      </button>
    );

  return (
    <div className="tg fade">
      <p>{t.profile.tgFor(user?.email ?? "")}</p>
      <p className="warn">{t.profile.tgWarn}</p>
      <div className="tg-acts">
        <a className="btn btn-ink btn-sm" href={link ?? "#"} target="_blank" rel="noreferrer" onClick={poll}>
          {t.profile.openApp}
        </a>
        <a className="btn btn-line btn-sm" href={webUrl} target="_blank" rel="noreferrer" onClick={poll}>
          {t.profile.openWeb}
        </a>
      </div>
      {command && (
        <label className="field-label">
          <small>{t.profile.manual}</small>
          <span className="tg-cmd">
            <input className="field-input" readOnly value={command} onFocus={(e) => e.currentTarget.select()} />
            <button className="btn btn-soft btn-sm" type="button" onClick={copy}>
              {t.profile.copy}
            </button>
          </span>
        </label>
      )}
      {state === "waiting" && (
        <p className="muted" role="status">
          {t.profile.waiting}
        </p>
      )}
      {state === "timeout" && (
        <p className="err" role="status">
          {t.profile.timeout}
        </p>
      )}
      <button
        className="linkish"
        type="button"
        onClick={() => {
          stop();
          setState("idle");
        }}
      >
        {t.common.cancel}
      </button>
    </div>
  );
}

function PlanCard() {
  const t = useT();
  const { user } = useAuth();
  const [asked, setAsked] = useState(false);
  const pro = hasPro(user);
  const adds = t.pro.benefits.slice(0, -1);

  return (
    <section className="card plan-card" id="plan" aria-labelledby="plan-h">
      <h2 id="plan-h">{t.profile.planH}</h2>
      <div className="v">{pro ? "Pro" : t.common.free}</div>
      {pro ? (
        <>
          <p style={{ marginTop: 12 }}>{user?.is_admin && user.plan !== "pro" ? t.profile.adminPro : t.profile.proOn}</p>
          <ul>
            {adds.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <Link className="btn btn-accent" to="/analytics" style={{ marginTop: 18 }}>
            {t.profile.openAnalytics}
          </Link>
        </>
      ) : (
        <>
          <p style={{ marginTop: 14 }}>{t.profile.proAdds}</p>
          <ul>
            {adds.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <div className="price">
            <b className="num">{eur(PRO_PRICE)}</b>
            <span>{t.pro.perMonth}</span>
          </div>
          <button className="btn btn-accent" type="button" onClick={() => setAsked(true)} aria-expanded={asked}>
            {t.pro.get}
          </button>
          {asked && (
            <p className="note fade" role="status">
              {t.pro.manualNote}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function AccountCard() {
  const t = useT();
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [busy, setBusy] = useState(false);
  const same = name.trim() === (user?.full_name ?? "");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (same) return;
    setBusy(true);
    try {
      await api.updateProfile(name.trim());
      await refreshUser();
      toast.success(t.profile.nameSaved);
    } catch {
      toast.error(t.profile.saveFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={save} aria-labelledby="acc-h">
      <h2 id="acc-h">{t.profile.accountH}</h2>
      <div className="fields">
        <label className="field-label">
          {t.profile.name}
          <input className="field-input" value={name} placeholder={t.profile.namePh} autoComplete="name" onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field-label">
          {t.profile.email}
          <input className="field-input" value={user?.email ?? ""} readOnly aria-describedby="email-n" />
          <small id="email-n">{t.profile.emailNote}</small>
        </label>
        <div>
          <button className="btn btn-ink btn-sm" type="submit" disabled={busy || same}>
            {t.profile.saveName}
          </button>
        </div>
      </div>
    </form>
  );
}

function ShopsCard() {
  const t = useT();
  const { user, updatePreferences } = useAuth();
  const [shops, setShops] = useState<Set<string>>(() => new Set(user?.preferences?.monitored_stores ?? []));
  const [brands, setBrands] = useState<Set<string>>(() => new Set(user?.preferences?.interested_brands ?? []));
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({ queryKey: ["filters"], queryFn: api.getFilters, staleTime: 10 * 60_000 });

  const all = useMemo(() => {
    const top = (data?.brands ?? []).slice().sort((a, b) => b.count - a.count).map((b) => b.label);
    const seen = new Set<string>();
    return [...BRAND_OPTIONS.filter((b) => b !== "YSL"), ...top].filter((b) => {
      const k = b.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [data]);
  const needle = q.trim().toLowerCase();
  const shown = needle ? all.filter((b) => b.toLowerCase().includes(needle)).slice(0, 40) : all.slice(0, 24);
  const list = [...brands].filter((b) => !shown.includes(b)).concat(shown);

  const flip = (set: React.Dispatch<React.SetStateAction<Set<string>>>, k: string) =>
    set((prev) => {
      const n = new Set(prev);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });

  async function save() {
    setBusy(true);
    try {
      await updatePreferences({ monitored_stores: [...shops], interested_brands: [...brands] });
      toast.success(t.profile.prefsSaved);
    } catch {
      toast.error(t.profile.saveFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" id="shops" aria-labelledby="shops-h">
      <h2 id="shops-h">{t.profile.shopsH}</h2>
      <p className="k">{t.profile.shopsP}</p>
      <div className="fields">
        <div className="field-label">
          {t.profile.shopsL}
          <div className="chips">
            {SHOPS.map((s) => (
              <button
                key={s.key}
                className="chip"
                type="button"
                aria-pressed={shops.has(s.key)}
                disabled={!s.live}
                title={s.live ? undefined : t.profile.soon}
                onClick={() => flip(setShops, s.key)}
                style={{ ...fieldStyle(s.key), ["--chip" as string]: "var(--field)", ["--chip-ink" as string]: "var(--ink)" } as React.CSSProperties}
              >
                <i aria-hidden="true" />
                {s.label}
              </button>
            ))}
          </div>
        </div>
        <div className="field-label">
          <span>
            {t.profile.brandsL} <small className="num">· {brands.size ? t.profile.picked(brands.size) : t.profile.noBrands}</small>
          </span>
          <input className="field-input" style={{ maxWidth: 360 }} type="search" placeholder={t.profile.findBrand} aria-label={t.profile.findBrand} value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="chips">
            {list.map((b) => (
              <button key={b} className="chip" type="button" aria-pressed={brands.has(b)} onClick={() => flip(setBrands, b)}>
                {b}
              </button>
            ))}
          </div>
        </div>
        <div>
          <button className="btn btn-ink btn-sm" type="button" onClick={save} disabled={busy}>
            {t.profile.savePrefs}
          </button>
        </div>
      </div>
    </section>
  );
}

function AlertsCard() {
  const t = useT();
  const { user, updatePreferences, refreshUser } = useAuth();
  const prefs = user?.preferences;
  const tgConnected = Boolean(prefs?.telegram_chat_id);
  const [mail, setMail] = useState((prefs?.notification_channels ?? []).includes("email"));
  const [tg, setTg] = useState((prefs?.notification_channels ?? []).includes("telegram"));
  const [th, setTh] = useState(prefs?.notification_threshold_percent ?? 5);
  const [busy, setBusy] = useState(false);

  // A chat linked on this page is switched on straight away.
  const wasConnected = useRef(tgConnected);
  useEffect(() => {
    if (tgConnected && !wasConnected.current) setTg(true);
    wasConnected.current = tgConnected;
  }, [tgConnected]);

  async function save() {
    setBusy(true);
    try {
      const ch: ("email" | "telegram")[] = [];
      if (mail) ch.push("email");
      if (tg && tgConnected) ch.push("telegram");
      await updatePreferences({ notification_channels: ch, notification_threshold_percent: th });
      toast.success(t.profile.alertsSaved);
    } catch {
      toast.error(t.profile.saveFailed);
    } finally {
      setBusy(false);
    }
  }

  async function unlink() {
    try {
      await api.disconnectTelegram();
      await refreshUser();
      setTg(false);
      toast.success(t.profile.tgDisconnected);
    } catch {
      toast.error(t.common.error);
    }
  }

  return (
    <section className="card" id="alerts" aria-labelledby="alerts-h">
      <h2 id="alerts-h">{t.profile.alertsH}</h2>
      <p className="k">{t.profile.alertsP}</p>
      <div className="rowx">
        <span>
          <b>{t.profile.emailCh}</b>
          <small>{t.profile.emailTo(user?.email ?? "")}</small>
        </span>
        <Switch on={mail} onChange={setMail} label={t.profile.emailCh} />
      </div>
      <div className="rowx">
        <span>
          <b>{t.profile.tgCh}</b>
          <small>
            {tgConnected ? t.profile.tgOn : t.profile.tgOff}
            {tgConnected && (
              <>
                {" · "}
                <button className="linkish" type="button" onClick={unlink}>
                  {t.profile.disconnect}
                </button>
              </>
            )}
          </small>
        </span>
        {tgConnected ? <Switch on={tg} onChange={setTg} label={t.profile.tgCh} /> : <TelegramConnect />}
      </div>
      <div className="rowx">
        <span>
          <b>{t.profile.thH}</b>
          <small>{t.profile.thP}</small>
        </span>
        <select className="sel" aria-label={t.profile.thH} value={th} onChange={(e) => setTh(Number(e.target.value))}>
          {t.profile.thOpts.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
      <div style={{ marginTop: 14 }}>
        <button className="btn btn-ink btn-sm" type="button" onClick={save} disabled={busy}>
          {t.profile.saveAlerts}
        </button>
      </div>
    </section>
  );
}

function PasswordCard() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (next.length < 8) return setErr(t.profile.pwShort);
    if (next !== again) return setErr(t.profile.pwMismatch);
    setErr(null);
    setBusy(true);
    try {
      await api.changePassword(cur, next);
      toast.success(t.profile.pwSaved);
      setCur("");
      setNext("");
      setAgain("");
      setOpen(false);
    } catch (e) {
      const m = e instanceof Error ? e.message : "";
      setErr(m.includes("incorrect") ? t.profile.pwWrong : m.includes("differ") ? t.profile.pwSame : t.common.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="pw-h">
      <h2 id="pw-h">{t.profile.pwH}</h2>
      {open ? (
        <form className="fields" onSubmit={submit}>
          <label className="field-label">
            {t.profile.pwCurrent}
            <input className="field-input" type="password" autoComplete="current-password" required value={cur} onChange={(e) => setCur(e.target.value)} />
          </label>
          <label className="field-label">
            <span>
              {t.profile.pwNew} <small>· {t.profile.pwHint}</small>
            </span>
            <input className="field-input" type="password" autoComplete="new-password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
          </label>
          <label className="field-label">
            {t.profile.pwRepeat}
            <input className="field-input" type="password" autoComplete="new-password" required value={again} onChange={(e) => setAgain(e.target.value)} />
          </label>
          {err && (
            <p className="err" role="alert">
              {err}
            </p>
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn-ink btn-sm" type="submit" disabled={busy}>
              {t.profile.pwChange}
            </button>
            <button className="btn btn-line btn-sm" type="button" onClick={() => setOpen(false)}>
              {t.common.cancel}
            </button>
          </div>
        </form>
      ) : (
        <button className="btn btn-soft btn-sm" type="button" onClick={() => setOpen(true)}>
          {t.profile.pwChange}
        </button>
      )}
    </section>
  );
}

function LeaveCard() {
  const t = useT();
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function remove() {
    setBusy(true);
    try {
      await api.deleteAccount();
      logout();
      nav("/", { replace: true });
    } catch {
      toast.error(t.common.error);
      setBusy(false);
    }
  }

  return (
    <>
      <section className="card" aria-labelledby="out-h">
        <h2 id="out-h">{t.profile.outH}</h2>
        <p className="k">{t.profile.outP}</p>
        <button
          className="btn btn-line btn-sm"
          type="button"
          onClick={() => {
            logout();
            nav("/", { replace: true });
          }}
        >
          {t.shell.signOut}
        </button>
      </section>
      <section className="card danger" aria-labelledby="del-h">
        <h2 id="del-h">{t.profile.dangerH}</h2>
        <p className="k">{t.profile.dangerP}</p>
        {ask ? (
          <div className="confirm fade" role="alertdialog" aria-labelledby="del-q">
            <span id="del-q">{t.profile.delAsk(user?.email ?? "")}</span>
            <span style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-red btn-sm" type="button" onClick={remove} disabled={busy}>
                {t.profile.delYes}
              </button>
              <button className="btn btn-line btn-sm" type="button" onClick={() => setAsk(false)}>
                {t.common.cancel}
              </button>
            </span>
          </div>
        ) : (
          <button className="btn btn-line btn-sm" type="button" style={{ color: "var(--up)" }} onClick={() => setAsk(true)}>
            {t.profile.del}
          </button>
        )}
      </section>
    </>
  );
}

export default function Profile() {
  const t = useT();
  const { user } = useAuth();
  const { hash } = useLocation();
  usePageContext(`User profile page. Plan: ${hasPro(user) ? "Pro" : "Free"}.`);

  // /profile#plan, #shops and #alerts are linked from the menu, Favorites and the Pro gate.
  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(hash.slice(1));
    if (el) requestAnimationFrame(() => el.scrollIntoView({ block: "start" }));
  }, [hash]);

  return (
    <AppShell>
      <div className="pg-profile">
        <section className="phead">
          <div>
            <h1>{user?.full_name || t.profile.title}</h1>
            <p className="sub">
              {user?.email} · {t.profile.sub(dayLong(user?.created_at))}
            </p>
          </div>
        </section>
        <div className="layout">
          <div className="col-a">
            <AccountCard />
            <ShopsCard />
            <AlertsCard />
            <PasswordCard />
          </div>
          <div className="col-b">
            <PlanCard />
            <section className="card" aria-labelledby="lang-h">
              <h2 id="lang-h">{t.profile.langH}</h2>
              <p className="k">{t.profile.langP}</p>
              <LangSwitch className="seg" />
            </section>
            <LeaveCard />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
