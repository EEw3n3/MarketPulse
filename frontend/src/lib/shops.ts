// Shops the scrapers cover. Each owns a pastel field (tiles, chips, legends)
// and a deeper line of the same hue for charts. `live: false` marks a shop
// whose scraper is blocked for now (1a.lv sits behind a Cloudflare check).

export type ShopKey = "notino" | "makeup" | "220" | "douglas" | "1a";

export interface Shop {
  key: ShopKey | string;
  label: string;
  domain: string;
  field: string;
  line: string;
  live: boolean;
}

export const SHOPS: Shop[] = [
  { key: "notino", label: "Notino", domain: "notino.lv", field: "var(--f-notino)", line: "#4766e8", live: true },
  { key: "makeup", label: "Makeup.lv", domain: "makeup.lv", field: "var(--f-makeup)", line: "#d9622b", live: true },
  { key: "220", label: "220.lv", domain: "220.lv", field: "var(--f-220)", line: "#3b8f22", live: true },
  { key: "douglas", label: "Douglas", domain: "douglas.lv", field: "var(--f-douglas)", line: "#b98a00", live: true },
  { key: "1a", label: "1a.lv", domain: "1a.lv", field: "var(--f-1a)", line: "#c2417a", live: false },
];

export const LIVE_SHOPS = SHOPS.filter((s) => s.live);

/** "Douglas Latvia", "makeup.lv", "Makeup.lv" -> "douglas", "makeup". */
export function shopKey(s: string | null | undefined): string {
  return (s || "")
    .toLowerCase()
    .trim()
    .replace(/\.lv$/, "")
    .replace(/\s*latvija$/, "")
    .replace(/\s*latvia$/, "")
    .trim();
}

export function shopOf(s: string | null | undefined): Shop {
  const key = shopKey(s);
  return (
    SHOPS.find((x) => x.key === key) ?? {
      key,
      label: s || "—",
      domain: key,
      field: "var(--surface)",
      line: "#63635f",
      live: true,
    }
  );
}

/** Inline style that sets the --field custom property for a shop. */
export function fieldStyle(s: string | null | undefined): React.CSSProperties {
  return { ["--field" as string]: shopOf(s).field } as React.CSSProperties;
}
