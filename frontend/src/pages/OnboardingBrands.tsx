import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Search, ArrowLeft, ArrowRight, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import logoImg from "@/assets/logo.png";

const BRANDS = [
  "Dior", "Chanel", "Tom Ford", "Versace", "Hugo Boss", "Armani",
  "Paco Rabanne", "Jean Paul Gaultier", "Creed", "Maison Margiela",
  "YSL", "Burberry", "Dolce & Gabbana", "Guerlain", "Givenchy",
  "Lacoste", "Calvin Klein", "Hermès", "Davidoff", "Montblanc",
  "Armaf", "Mancera", "Afnan", "Lattafa", "Rasasi",
  "Attar Collection", "Parfums de Marly", "Initio", "Memo Paris", "Xerjoff",
];

// Group brands for a bit of editorial structure
const GROUPS: { label: string; brands: string[] }[] = [
  { label: "Designer", brands: ["Dior", "Chanel", "Tom Ford", "Versace", "Hugo Boss", "Armani", "YSL", "Burberry", "Dolce & Gabbana", "Givenchy", "Lacoste", "Calvin Klein", "Hermès"] },
  { label: "Niche", brands: ["Creed", "Maison Margiela", "Guerlain", "Attar Collection", "Parfums de Marly", "Initio", "Memo Paris", "Xerjoff", "Mancera"] },
  { label: "Middle East", brands: ["Armaf", "Afnan", "Lattafa", "Rasasi"] },
  { label: "Men's classics", brands: ["Paco Rabanne", "Jean Paul Gaultier", "Davidoff", "Montblanc"] },
];

export default function OnboardingBrands() {
  const { updatePreferences, user } = useAuth();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<string>>(
    new Set(user?.preferences?.interested_brands ?? [])
  );
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  const toggle = (b: string) =>
    setSelected((prev) => {
      const n = new Set(prev);
      n.has(b) ? n.delete(b) : n.add(b);
      return n;
    });

  const query = search.trim().toLowerCase();

  const visibleGroups = useMemo(() => {
    if (!query) return GROUPS;
    return GROUPS.map((g) => ({
      ...g,
      brands: g.brands.filter((b) => b.toLowerCase().includes(query)),
    })).filter((g) => g.brands.length > 0);
  }, [query]);

  const finish = async (skip = false) => {
    setLoading(true);
    try {
      await updatePreferences({
        interested_brands: skip ? [] : [...selected],
        onboarding_completed: true,
      });
      navigate("/dashboard", { replace: true, state: { showTutorial: true } });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background grid grid-cols-1 lg:grid-cols-[480px_1fr]">
      {/* ═════════════════ LEFT — Editorial ═════════════════ */}
      <aside className="relative hidden lg:flex flex-col justify-between bg-surface/40 border-r border-border px-12 py-10 overflow-hidden">
        <div
          aria-hidden
          className="absolute right-[-100px] bottom-[-100px] w-[440px] h-[440px] rounded-full pointer-events-none"
          style={{ background: "hsl(var(--primary))", filter: "blur(160px)", opacity: 0.08 }}
        />

        <div className="relative flex items-center gap-2.5">
          <img src={logoImg} alt="MarketPulse" className="h-8 w-auto" />
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            Setup
          </span>
        </div>

        <div className="relative max-w-sm">
          <span className="inline-block text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-6">
            <span className="text-muted-foreground/60">01 / </span>
            <span className="text-primary">02</span> · <span className="text-foreground">Watchlist</span>
          </span>

          <h1 className="font-['Inter'] font-semibold text-foreground text-[36px] leading-[1.1] tracking-[-0.02em]">
            Who's on
            <br />
            your watchlist?
          </h1>

          <p className="mt-5 text-[14px] text-muted-foreground leading-[1.6]">
            Brands on your list get priority in the feed and AI analysis. Leave empty to see everything
            — you can always tune it later.
          </p>

          <div className="mt-10 border-t border-border pt-5 space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] text-muted-foreground">Selected</span>
              <span className="font-mono text-[14px] text-foreground">
                {selected.size.toString().padStart(2, "0")}
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] text-muted-foreground">Suggested</span>
              <span className="font-mono text-[12px] text-muted-foreground">3 — 8 brands</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] text-muted-foreground">Catalog</span>
              <span className="font-mono text-[12px] text-muted-foreground">{BRANDS.length} options</span>
            </div>
          </div>
        </div>

        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-0.5 flex-1 bg-primary/40" />
            <span className="h-0.5 flex-1 bg-primary" />
          </div>
          <div className="flex items-center justify-between font-mono text-[11px] text-muted-foreground">
            <span>Step 01 — Coverage</span>
            <span className="text-foreground">Step 02 — Brands</span>
          </div>
        </div>
      </aside>

      {/* ═════════════════ RIGHT — Selection ═════════════════ */}
      <main className="flex flex-col px-6 sm:px-10 lg:px-16 py-8">
        <div className="flex items-center justify-between">
          <div className="flex lg:hidden items-center gap-2">
            <img src={logoImg} alt="MarketPulse" className="h-7 w-auto" />
          </div>
          <p className="lg:hidden text-[11px] font-mono text-muted-foreground">02 / 02</p>
          <button
            onClick={() => finish(true)}
            disabled={loading}
            className="hidden lg:inline-flex text-[12px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          >
            Skip — show all brands
          </button>
        </div>

        <div className="flex-1 flex flex-col justify-center max-w-2xl w-full mx-auto lg:mx-0 py-10">
          <div className="lg:hidden mb-8">
            <h1 className="font-['Inter'] font-semibold text-foreground text-[28px] leading-[1.15] tracking-[-0.01em]">
              Who's on your watchlist?
            </h1>
            <p className="text-[14px] text-muted-foreground mt-2">
              Pick the brands you want prioritized.
            </p>
          </div>

          {/* Search */}
          <div className="relative mb-6">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search brands…"
              className="w-full bg-surface border border-border rounded-md pl-10 pr-10 py-2.5 text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Grouped brand chips */}
          <div className="space-y-6 max-h-[54vh] overflow-y-auto pr-2 -mr-2">
            {visibleGroups.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">No brands match "{search}".</p>
            ) : (
              visibleGroups.map((group) => (
                <div key={group.label}>
                  <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-medium mb-3">
                    {group.label}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {group.brands.map((brand) => {
                      const active = selected.has(brand);
                      return (
                        <button
                          key={brand}
                          onClick={() => toggle(brand)}
                          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-[13px] border transition-colors
                            ${active
                              ? "bg-foreground text-background border-foreground"
                              : "bg-surface border-border text-muted-foreground hover:border-muted-foreground hover:text-foreground"
                            }`}
                        >
                          {active && <Check className="w-3 h-3" strokeWidth={3} />}
                          {brand}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex items-center justify-between mt-8 pt-6 border-t border-border">
            <p className="text-[12px] text-muted-foreground">
              {selected.size === 0 ? (
                <span>No brands selected — feed will show everything.</span>
              ) : (
                <span>
                  <span className="text-foreground font-medium">{selected.size}</span> brand
                  {selected.size === 1 ? "" : "s"} prioritized.
                </span>
              )}
            </p>

            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/onboarding/stores")}
                className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
              <button
                disabled={loading}
                onClick={() => finish(false)}
                className="inline-flex items-center gap-1.5 bg-foreground text-background rounded-md px-5 py-2.5 text-[14px] font-medium hover:bg-foreground/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Finishing…" : "Finish setup"}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground font-mono text-center lg:text-left">
          marketpulse.lv · You can re-tune brands anytime in Settings
        </p>
      </main>
    </div>
  );
}
