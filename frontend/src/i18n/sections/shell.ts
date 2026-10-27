const en = {
  nav: { today: "Today", catalog: "Catalogue", favorites: "Favorites", analytics: "Analytics", admin: "Admin", profile: "Profile" },
  mainNav: "Main",
  skip: "Skip to content",
  searchLabel: "Search perfumes",
  searchPlaceholder: "Search perfumes",
  matching: "Matching perfumes",
  noMatch: "No perfume matches. Try the brand or fewer words.",
  allResults: (q: string) => `All results for “${q}” in the catalogue`,
  language: "Language",
  account: "Account",
  signedInAs: "Signed in as",
  planFree: "Free plan",
  planPro: "Pro plan",
  admin: "Admin",
  getPro: "Get Pro",
  signOut: "Sign out",
};

const lv: typeof en = {
  nav: { today: "Šodien", catalog: "Katalogs", favorites: "Izlase", analytics: "Analītika", admin: "Admin", profile: "Profils" },
  mainNav: "Galvenā navigācija",
  skip: "Pāriet uz saturu",
  searchLabel: "Meklēt smaržas",
  searchPlaceholder: "Meklēt smaržas",
  matching: "Atbilstošās smaržas",
  noMatch: "Nekas neatbilst. Mēģiniet zīmolu vai mazāk vārdu.",
  allResults: (q) => `Visi rezultāti “${q}” katalogā`,
  language: "Valoda",
  account: "Konts",
  signedInAs: "Pierakstījies kā",
  planFree: "Bezmaksas plāns",
  planPro: "Pro plāns",
  admin: "Administrators",
  getPro: "Iegūt Pro",
  signOut: "Izrakstīties",
};

export default { en, lv };
