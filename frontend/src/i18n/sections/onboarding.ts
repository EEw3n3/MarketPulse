import { plural } from "../plural";

const en = {
  step: (n: number, of: number) => `Step ${n} of ${of}`,
  storesH: "Which shops do you buy from?",
  storesP: "Today shows price drops in these shops first. You can change this any time in your profile.",
  listings: (n: number) => plural(n, { one: "listing", other: "listings" }),
  soon: "Data on the way",
  selectAll: "Select all",
  brandsH: "Which brands do you follow?",
  brandsP: "Pick a few, and Today puts their price drops at the top. Skip if you like everything.",
  findBrand: "Find a brand",
  picked: (n: number) => plural(n, { one: "brand picked", other: "brands picked" }),
  skip: "Skip",
  finish: "Show my Today",
  failed: "Could not save. Try again.",
};

const lv: typeof en = {
  step: (n, of) => `${n}. solis no ${of}`,
  storesH: "Kuros veikalos jūs pērkat?",
  storesP: "Sadaļā Šodien vispirms būs cenu kritumi šajos veikalos. To var mainīt jebkurā laikā profilā.",
  listings: (n) => plural(n, { one: "piedāvājums", other: "piedāvājumi", zero: "piedāvājumu" }),
  soon: "Dati drīzumā",
  selectAll: "Atlasīt visus",
  brandsH: "Kuriem zīmoliem jūs sekojat?",
  brandsP: "Izvēlieties dažus, un sadaļā Šodien to cenu kritumi būs augšā. Izlaidiet, ja patīk viss.",
  findBrand: "Atrast zīmolu",
  picked: (n) => plural(n, { one: "zīmols izvēlēts", other: "zīmoli izvēlēti", zero: "zīmolu izvēlēts" }),
  skip: "Izlaist",
  finish: "Rādīt manu Šodien",
  failed: "Neizdevās saglabāt. Mēģiniet vēlreiz.",
};

export default { en, lv };
