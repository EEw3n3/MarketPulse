import { locale } from "@/lib/format";

export interface Forms {
  one: string;
  other: string;
  /** Latvian uses the genitive plural for 0, 10–20, 30… ("0 smaržu"). */
  zero?: string;
}

const rules = new Map<string, Intl.PluralRules>();

/** "1 perfume", "3 perfumes"; picks the form with the current locale's rules. */
export function plural(n: number, f: Forms, withNumber = true): string {
  const loc = locale();
  let r = rules.get(loc);
  if (!r) {
    r = new Intl.PluralRules(loc);
    rules.set(loc, r);
  }
  const cat = r.select(n);
  const word = cat === "one" ? f.one : cat === "zero" && f.zero ? f.zero : f.other;
  return withNumber ? `${new Intl.NumberFormat(loc).format(n)} ${word}` : word;
}
