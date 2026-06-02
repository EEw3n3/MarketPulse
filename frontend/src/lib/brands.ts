// Curated brand list — shown in onboarding and the dashboard "+ Add" picker.
// Catalog page uses a dynamic list from /api/products/brands instead.

export const BRAND_OPTIONS: string[] = [
  "Dior", "Chanel", "Tom Ford", "Versace", "Hugo Boss", "Armani",
  "Paco Rabanne", "Jean Paul Gaultier", "Creed", "Maison Margiela",
  "YSL", "Burberry", "Dolce & Gabbana", "Guerlain", "Givenchy",
  "Lacoste", "Calvin Klein", "Hermès", "Davidoff", "Montblanc",
  "Armaf", "Mancera", "Afnan", "Lattafa", "Rasasi",
  "Attar Collection", "Parfums de Marly", "Initio", "Memo Paris", "Xerjoff",
];

// Quick-pick brands shown directly as chips in DashboardFilterBar (the rest
// live behind the "+ Add" sheet).
export const QUICK_PICK_BRANDS: string[] = [
  "Dior", "Hugo Boss", "Versace", "Armani", "Paco Rabanne",
];

// Short brand aliases ↔ full canonical forms (mirrors backend
// normalizer.BRAND_ALIASES). Used when comparing a user's preferred brands
// (which may be shorthand like "YSL") against product.brand values (stored
// as the full name "Yves Saint Laurent"). Lowercased keys.
const BRAND_ALIAS_PAIRS: [string, string][] = [
  ["jpg", "jean paul gaultier"],
  ["ysl", "yves saint laurent"],
  ["d&g", "dolce & gabbana"],
  ["mfk", "maison francis kurkdjian"],
  ["v&r", "viktor & rolf"],
  ["fitch", "abercrombie & fitch"],
];

/** Expand a brand name to all equivalent lowercase forms (itself + any alias
 * counterpart in either direction). E.g. "YSL" → ["ysl", "yves saint laurent"]. */
export function expandBrandAliases(brand: string): string[] {
  const low = brand.toLowerCase().trim();
  const out = new Set<string>([low]);
  for (const [short, long] of BRAND_ALIAS_PAIRS) {
    if (low === short) out.add(long);
    else if (low === long) out.add(short);
  }
  return Array.from(out);
}
