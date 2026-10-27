import { useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import { api } from "@/lib/api";
import { int } from "@/lib/format";
import LangSwitch from "@/components/mp/LangSwitch";

/** Only same-site paths, so a crafted ?next= cannot send people elsewhere. */
function safeNext(v: string | null): string | null {
  return v && v.startsWith("/") && !v.startsWith("//") ? v : null;
}

function errorOf(e: unknown): { status: number; detail: string } {
  const m = (e instanceof Error ? e.message : "").match(/^API Error:\s*(\d+)\s*(.*)$/);
  return { status: m ? Number(m[1]) : 0, detail: m ? m[2].trim() : "" };
}

/** Sign in and registration share one two-column layout. */
export default function Auth({ mode }: { mode: "signin" | "register" }) {
  const t = useT();
  const { user, login, register } = useAuth();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({ queryKey: ["landing"], queryFn: api.getLanding, staleTime: 10 * 60_000 });

  if (user) {
    const target = user.preferences?.onboarding_completed ? next ?? "/today" : "/onboarding/stores";
    return <Navigate to={target} replace />;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (mode === "register" && password.length < 8) {
      setError(t.auth.short);
      return;
    }
    setBusy(true);
    try {
      if (mode === "signin") await login(email, password);
      else await register(email, password, name.trim() || undefined);
    } catch (err) {
      const { status, detail } = errorOf(err);
      if (mode === "signin") setError(status === 401 ? t.auth.badLogin : status === 403 && detail ? detail : t.auth.failed);
      else setError(status === 409 ? t.auth.taken : detail || t.auth.failed);
    } finally {
      setBusy(false);
    }
  }

  const reg = mode === "register";
  return (
    <div className="pg-auth">
      <aside className="side" style={{ ["--field" as string]: reg ? "var(--f-makeup)" : "var(--f-notino)" } as React.CSSProperties}>
        <Link className="logo" to="/">
          MarketPulse
        </Link>
        <h1 className="display">
          <span className="line">
            <span style={{ ["--i" as string]: 0 } as React.CSSProperties}>{t.auth.sideTitle[0]}</span>
          </span>
          <span className="line">
            <span style={{ ["--i" as string]: 1 } as React.CSSProperties}>{t.auth.sideTitle[1]}</span>
          </span>
        </h1>
        <div style={{ display: "grid", gap: 18 }}>
          <ul>
            {t.auth.sideList.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <div className="facts num">
            {data && <span>{t.auth.sideFacts(int(data.market.current_products))}</span>}
            <span>Notino · Makeup.lv · 220.lv · Douglas</span>
          </div>
        </div>
      </aside>
      <div className="main">
        <div className="main-top">
          <Link className="linkish" to="/">
            ← {t.auth.home}
          </Link>
          <LangSwitch />
        </div>
        <div className="form-wrap">
          <form onSubmit={submit} noValidate>
            <h2>{reg ? t.auth.registerH : t.auth.signInH}</h2>
            {reg && (
              <label className="field-label">
                <span>
                  {t.auth.name} <small>{t.auth.nameHint}</small>
                </span>
                <input className="field-input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={100} />
              </label>
            )}
            <label className="field-label">
              {t.auth.email}
              <input className="field-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus />
            </label>
            <label className="field-label">
              <span>
                {t.auth.password} {reg && <small>{t.auth.passwordHint}</small>}
              </span>
              <span className="pw">
                <input
                  className="field-input"
                  type={show ? "text" : "password"}
                  required
                  minLength={reg ? 8 : undefined}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={reg ? "new-password" : "current-password"}
                />
                <button type="button" onClick={() => setShow((s) => !s)} aria-pressed={show}>
                  {show ? t.auth.hide : t.auth.show}
                </button>
              </span>
            </label>
            {error && (
              <p className="err" role="alert">
                {error}
              </p>
            )}
            <button className="btn btn-ink" type="submit" disabled={busy || !email || !password}>
              {busy ? t.common.loading : reg ? t.auth.register : t.auth.signIn}
            </button>
            <p className="alt">
              {reg ? (
                <>
                  {t.auth.haveAccount} <Link to={`/signin${next ? `?next=${encodeURIComponent(next)}` : ""}`}>{t.auth.toSignIn}</Link>
                  <br />
                  {t.auth.terms}
                </>
              ) : (
                <>
                  {t.auth.noAccount} <Link to={`/register${next ? `?next=${encodeURIComponent(next)}` : ""}`}>{t.auth.toRegister}</Link>
                </>
              )}
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
