import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setFormatLocale } from "@/lib/format";
import common from "./sections/common";
import shell from "./sections/shell";
import chat from "./sections/chat";
import pro from "./sections/pro";
import exporter from "./sections/exporter";
import landing from "./sections/landing";
import auth from "./sections/auth";
import onboarding from "./sections/onboarding";
import today from "./sections/today";
import catalog from "./sections/catalog";
import product from "./sections/product";
import favorites from "./sections/favorites";
import analytics from "./sections/analytics";
import profile from "./sections/profile";
import admin from "./sections/admin";

export type Lang = "en" | "lv";

const sections = {
  common,
  shell,
  chat,
  pro,
  exporter,
  landing,
  auth,
  onboarding,
  today,
  catalog,
  product,
  favorites,
  analytics,
  profile,
  admin,
};
type Sections = typeof sections;
export type Dict = { [K in keyof Sections]: Sections[K]["en"] };

function build(lang: Lang): Dict {
  const out = {} as Record<string, unknown>;
  for (const [k, v] of Object.entries(sections)) out[k] = v[lang];
  return out as Dict;
}
const DICTS: Record<Lang, Dict> = { en: build("en"), lv: build("lv") };

const KEY = "marketpulse_lang";

function initialLang(): Lang {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "en" || v === "lv") return v;
  } catch {
    /* storage blocked */
  }
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("lv") ? "lv" : "en";
}

interface I18nValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Dict;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  // Before children render, so their number and date formats follow.
  setFormatLocale(lang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* storage blocked */
    }
  }, []);

  const value = useMemo(() => ({ lang, setLang, t: DICTS[lang] }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

export function useT(): Dict {
  return useI18n().t;
}
