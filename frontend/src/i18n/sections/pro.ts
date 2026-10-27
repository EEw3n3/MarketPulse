import { plural } from "../plural";

const en = {
  tag: "PRO",
  perMonth: "/ month",
  title: "MarketPulse Pro",
  pitch: "The whole Latvian perfume market in one place: which shop is cheapest, how prices move and where the gaps are.",
  benefits: [
    "Market analytics: price index per shop, who is cheapest, biggest moves and gaps",
    "Export to Excel, PDF, CSV and JSON",
    "Pick catalogue rows and export only those",
    "Brand × shop price map and price bands",
    "Everything in Free",
  ],
  freeBenefits: [
    "Catalogue of every shop with full filters",
    "Product pages with price history",
    "Favorites with drop alerts",
    "AI assistant on every page",
  ],
  get: "Get Pro",
  manualNote: "Card payments are coming soon. Until then the MarketPulse team switches Pro on by hand. Ask in the chat or write to the team, and your account gets it within a day.",
  locked: "Pro feature",
  lockedExport: "Export is part of Pro",
  youHave: "You have Pro",
  adminHas: "Admins have every Pro feature",
  gateKicker: "Pro analytics",
  gateTitle: "See the whole market, not one bottle",
  locks: ["Price index per shop", "Who is cheapest", "Biggest moves", "Gaps between shops", "Brand × shop map", "Export in 4 formats"],
  preview: "Preview with sample shapes",
  comparable: (n: number) => plural(n, { one: "bottle compared", other: "bottles compared" }),
};

const lv: typeof en = {
  tag: "PRO",
  perMonth: "/ mēnesī",
  title: "MarketPulse Pro",
  pitch: "Viss Latvijas smaržu tirgus vienuviet: kurš veikals ir lētākais, kā mainās cenas un kur ir lielākās atšķirības.",
  benefits: [
    "Tirgus analītika: cenu indekss pa veikaliem, kurš ir lētākais, lielākās izmaiņas un atšķirības",
    "Eksports uz Excel, PDF, CSV un JSON",
    "Izvēlieties kataloga rindas un eksportējiet tikai tās",
    "Zīmolu × veikalu cenu karte un cenu diapazoni",
    "Viss, kas ir bezmaksas plānā",
  ],
  freeBenefits: [
    "Visu veikalu katalogs ar pilniem filtriem",
    "Produktu lapas ar cenu vēsturi",
    "Izlase ar paziņojumiem par cenu kritumu",
    "AI asistents katrā lapā",
  ],
  get: "Iegūt Pro",
  manualNote: "Maksājumi ar karti būs drīzumā. Līdz tam MarketPulse komanda ieslēdz Pro manuāli. Pajautājiet čatā vai rakstiet komandai, un jūsu konts to saņems dienas laikā.",
  locked: "Pro funkcija",
  lockedExport: "Eksports ir daļa no Pro",
  youHave: "Jums ir Pro",
  adminHas: "Administratoriem ir visas Pro funkcijas",
  gateKicker: "Pro analītika",
  gateTitle: "Redziet visu tirgu, ne tikai vienu pudeli",
  locks: ["Cenu indekss pa veikaliem", "Kurš ir lētākais", "Lielākās izmaiņas", "Atšķirības starp veikaliem", "Zīmolu × veikalu karte", "Eksports 4 formātos"],
  preview: "Priekšskatījums ar parauga formām",
  comparable: (n) => plural(n, { one: "salīdzināta pudele", other: "salīdzinātas pudeles", zero: "salīdzinātu pudeļu" }),
};

export default { en, lv };
