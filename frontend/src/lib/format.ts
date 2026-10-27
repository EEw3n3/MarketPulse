// Number and date formatting in the interface language. The I18nProvider sets
// the locale before its children render, so every component that reads the
// dictionary re-renders with the new locale too.

let LOCALE = "en-IE";
const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>();

export function setFormatLocale(lang: "en" | "lv") {
  const next = lang === "lv" ? "lv-LV" : "en-IE";
  if (next !== LOCALE) {
    LOCALE = next;
    cache.clear();
  }
}

function nf(digits: number, currency = false): Intl.NumberFormat {
  const k = `n${digits}${currency ? "c" : ""}`;
  let f = cache.get(k) as Intl.NumberFormat | undefined;
  if (!f) {
    f = new Intl.NumberFormat(LOCALE, {
      ...(currency ? { style: "currency", currency: "EUR" } : {}),
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    cache.set(k, f);
  }
  return f;
}

function df(opts: Intl.DateTimeFormatOptions, key: string): Intl.DateTimeFormat {
  let f = cache.get(key) as Intl.DateTimeFormat | undefined;
  if (!f) {
    f = new Intl.DateTimeFormat(LOCALE, opts);
    cache.set(key, f);
  }
  return f;
}

/** €42.50 / 42,50 € */
export function eur(v: number | null | undefined, digits = 2): string {
  return v == null || Number.isNaN(v) ? "—" : nf(digits, true).format(v);
}

/** Whole euros for big figures. */
export function eur0(v: number | null | undefined): string {
  return eur(v == null ? v : Math.round(v), 0);
}

/** −12% / +3.5% with a true minus sign. */
export function pct(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return "—";
  const r = Number(Math.abs(v).toFixed(digits));
  if (r === 0) return nf(0).format(0) + "%";
  return (v > 0 ? "+" : "−") + nf(digits).format(r) + "%";
}

/** Plain percent without a sign. */
export function pctPlain(v: number | null | undefined, digits = 0): string {
  return v == null ? "—" : nf(digits).format(v) + "%";
}

export function int(v: number | null | undefined): string {
  return v == null ? "—" : nf(0).format(v);
}

export function num(v: number | null | undefined, digits = 1): string {
  return v == null ? "—" : nf(digits).format(v);
}

function toDate(v: string | Date): Date {
  if (v instanceof Date) return v;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return new Date(v + "T12:00:00Z");
  // The API stores UTC without a zone suffix; read it as UTC, not local time.
  return new Date(/T[\d:.]+$/.test(v) ? v + "Z" : v);
}

/** 26 Oct */
export function day(v: string | Date | null | undefined): string {
  if (!v) return "—";
  return df({ day: "numeric", month: "short", timeZone: "Europe/Riga" }, "d").format(toDate(v));
}

/** 26 October 2026 */
export function dayLong(v: string | Date | null | undefined): string {
  if (!v) return "—";
  return df({ day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Riga" }, "dl").format(toDate(v));
}

/** 26 Oct, 04:12 */
export function dateTime(v: string | Date | null | undefined): string {
  if (!v) return "—";
  return df(
    { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Riga" },
    "dt",
  ).format(toDate(v));
}

/** "3 hours ago", "yesterday" */
export function ago(v: string | Date | null | undefined): string {
  if (!v) return "—";
  const s = (Date.now() - toDate(v).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  if (s < 60) return rtf.format(0, "second");
  if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
  if (s < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  if (s < 86400 * 30) return rtf.format(-Math.round(s / 86400), "day");
  return day(v);
}

/** Days between an ISO timestamp and now. */
export function daysSince(v: string | null | undefined): number | null {
  if (!v) return null;
  return Math.floor((Date.now() - toDate(v).getTime()) / 86400000);
}

export function locale(): string {
  return LOCALE;
}
