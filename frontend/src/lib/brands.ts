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
