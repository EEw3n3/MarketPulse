import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import { api } from "@/lib/api";
import { BRAND_OPTIONS } from "@/lib/brands";
import { SHOPS, fieldStyle } from "@/lib/shops";
import LangSwitch from "@/components/mp/LangSwitch";

function Head({ step }: { step: 1 | 2 }) {
  const t = useT();
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
      <Link className="logo" to="/">
        MarketPulse
      </Link>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span className="muted" style={{ fontSize: 14 }}>
          {t.onboarding.step(step, 2)}
        </span>
        <div className="steps" aria-hidden="true">
          <i className="on" />
          <i className={step === 2 ? "on" : ""} />
        </div>
        <LangSwitch />
      </div>
    </div>
  );
}

export function OnboardingStores() {
  const t = useT();
  const nav = useNavigate();
  const { user, updatePreferences } = useAuth();
  const [sel, setSel] = useState<Set<string>>(() => new Set(user?.preferences?.monitored_stores ?? []));
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({ queryKey: ["filters"], queryFn: api.getFilters, staleTime: 10 * 60_000 });
  const counts = new Map((data?.stores ?? []).map((s) => [s.value, s.count]));
  const live = SHOPS.filter((s) => s.live);

  const toggle = (k: string) =>
    setSel((prev) => {
      const n = new Set(prev);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });

  async function next() {
    setBusy(true);
    try {
      await updatePreferences({ monitored_stores: [...sel] });
      nav("/onboarding/brands");
    } catch {
      toast.error(t.onboarding.failed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pg-onb wrap">
      <Head step={1} />
      <div className="phead" style={{ paddingBottom: 0 }}>
        <div>
          <h1>{t.onboarding.storesH}</h1>
          <p className="sub">{t.onboarding.storesP}</p>
        </div>
        <button className="btn btn-soft btn-sm" type="button" onClick={() => setSel(new Set(live.map((s) => s.key)))}>
          {t.onboarding.selectAll}
        </button>
      </div>
      <div className="grid">
        {SHOPS.map((s, i) => (
          <button
            key={s.key}
            className="shopc rise"
            type="button"
            aria-pressed={sel.has(s.key)}
            disabled={!s.live}
            onClick={() => toggle(s.key)}
            style={{ ...fieldStyle(s.key), ["--i" as string]: i } as React.CSSProperties}
          >
            <b>{s.label}</b>
            <small className="num">{s.live ? (counts.get(s.key) ? t.onboarding.listings(counts.get(s.key)!) : s.domain) : t.onboarding.soon}</small>
          </button>
        ))}
      </div>
      <div className="foot wrap">
        <Link className="linkish" to="/today">
          {t.onboarding.skip}
        </Link>
        <button className="btn btn-ink" type="button" onClick={next} disabled={busy}>
          {t.common.next}
        </button>
      </div>
    </div>
  );
}

export function OnboardingBrands() {
  const t = useT();
  const nav = useNavigate();
  const { user, updatePreferences } = useAuth();
  const [sel, setSel] = useState<Set<string>>(() => new Set(user?.preferences?.interested_brands ?? []));
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const { data } = useQuery({ queryKey: ["filters"], queryFn: api.getFilters, staleTime: 10 * 60_000 });

  // Curated names first, then the brands with the most bottles.
  const brands = useMemo(() => {
    const top = (data?.brands ?? []).slice().sort((a, b) => b.count - a.count).map((b) => b.label);
    const all = [...BRAND_OPTIONS.filter((b) => b !== "YSL"), ...top];
    const seen = new Set<string>();
    return all.filter((b) => {
      const k = b.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [data]);
  const shown = q.trim() ? brands.filter((b) => b.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 60) : brands.slice(0, 48);

  async function finish(skip: boolean) {
    setBusy(true);
    try {
      await updatePreferences({ interested_brands: skip ? [] : [...sel], onboarding_completed: true });
      nav("/today", { replace: true });
    } catch {
      toast.error(t.onboarding.failed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pg-onb wrap">
      <Head step={2} />
      <div className="phead" style={{ paddingBottom: 0 }}>
        <div>
          <h1>{t.onboarding.brandsH}</h1>
          <p className="sub">{t.onboarding.brandsP}</p>
        </div>
      </div>
      <input className="field-input" style={{ maxWidth: 420 }} type="search" placeholder={t.onboarding.findBrand} aria-label={t.onboarding.findBrand} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips">
        {[...sel].filter((b) => !shown.includes(b)).concat(shown).map((b) => (
          <button
            key={b}
            className="chip"
            type="button"
            aria-pressed={sel.has(b)}
            onClick={() =>
              setSel((prev) => {
                const n = new Set(prev);
                if (n.has(b)) n.delete(b);
                else n.add(b);
                return n;
              })
            }
          >
            {b}
          </button>
        ))}
      </div>
      <div className="foot wrap">
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <Link className="linkish" to="/onboarding/stores">
            ← {t.common.back}
          </Link>
          <span className="muted num" style={{ fontSize: 14 }}>
            {t.onboarding.picked(sel.size)}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-line" type="button" onClick={() => finish(true)} disabled={busy}>
            {t.onboarding.skip}
          </button>
          <button className="btn btn-ink" type="button" onClick={() => finish(false)} disabled={busy}>
            {t.onboarding.finish}
          </button>
        </div>
      </div>
    </div>
  );
}
