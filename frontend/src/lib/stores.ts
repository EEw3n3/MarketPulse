// Canonical store keys — used for URL params and filter comparisons.
// `Product.search_term` in the DB is inconsistent: "Notino", "notino.lv",
// "Douglas Latvia", "Makeup latvija", "1A.LV". To filter reliably we always
// pass a normalized key to the backend, which then does case-insensitive
// substring matching.

export interface StoreOption {
  label: string;  // Display name
  key: string;    // Canonical key used in URL params and backend filter
}

export const STORE_OPTIONS: StoreOption[] = [
  { label: "Douglas",   key: "douglas" },
  { label: "Notino",    key: "notino"  },
  { label: "220.lv",    key: "220"     },
  { label: "Makeup.lv", key: "makeup"  },
  { label: "1a.lv",     key: "1a"      },
];

export const STORE_LABELS = STORE_OPTIONS.map((s) => s.label);

// Canonical keys for stores whose scraper integration is temporarily blocked
// (e.g. Cloudflare Managed Challenge on 1a.lv). The UI greys these out in
// filter lists with a "Data integration in progress" tooltip so users don't
// expect catalog rows from them.
export const UNAVAILABLE_STORE_KEYS = new Set<string>(["1a"]);

export function isStoreUnavailable(keyOrLabel: string): boolean {
  return UNAVAILABLE_STORE_KEYS.has(canonicalStore(keyOrLabel));
}

/** Normalizes any store-name variant ("Douglas Latvia", "douglas.lv", "Douglas")
 * to its canonical key ("douglas"). */
export function canonicalStore(s: string): string {
  return s
    .toLowerCase()
    .replace(/\.lv$/, "")
    .replace(/\s*latvija$/, "")
    .replace(/\s*latvia$/, "")
    .trim();
}

export function storeKeyFromLabel(label: string): string {
  const found = STORE_OPTIONS.find((s) => s.label === label);
  return found ? found.key : canonicalStore(label);
}

export function labelFromStoreKey(key: string): string {
  const found = STORE_OPTIONS.find((s) => s.key === key);
  return found ? found.label : key;
}
