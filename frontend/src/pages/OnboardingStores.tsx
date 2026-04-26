import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ArrowLeft, ArrowRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import logoImg from "@/assets/logo.png";

import storeDouglas from "@/assets/store-douglas.png";
import storeNotino from "@/assets/store-notino.png";
import store220 from "@/assets/store-220.png";
import storeMakeup from "@/assets/store-makeup.png";
import store1a from "@/assets/store-1a.png";

const STORES = [
  { id: "douglas", name: "Douglas.lv", stat: "273 products", tag: "Premium beauty", logo: storeDouglas },
  { id: "notino", name: "Notino.lv", stat: "1 000+ listings", tag: "Widest catalog", logo: storeNotino },
  { id: "makeup", name: "Makeup.lv", stat: "890 products", tag: "Local pricing", logo: storeMakeup },
  { id: "1a", name: "1a.lv", stat: "320 products", tag: "Marketplace", logo: store1a },
  { id: "220", name: "220.lv", stat: "540 products", tag: "Marketplace", logo: store220 },
];

export default function OnboardingStores() {
  const { updatePreferences, user } = useAuth();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<string>>(
    new Set(user?.preferences?.monitored_stores ?? [])
  );
  const [loading, setLoading] = useState(false);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const selectAll = () => setSelected(new Set(STORES.map((s) => s.id)));

  const handleNext = async () => {
    setLoading(true);
    try {
      await updatePreferences({ monitored_stores: [...selected] });
      navigate("/onboarding/brands");
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
          className="absolute left-[-120px] top-[-80px] w-[440px] h-[440px] rounded-full pointer-events-none"
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
            <span className="text-primary">01</span> · <span className="text-foreground">Coverage</span>
            <span className="text-muted-foreground/60"> / 02</span>
          </span>

          <h1 className="font-['Inter'] font-semibold text-foreground text-[36px] leading-[1.1] tracking-[-0.02em]">
            Choose
            <br />
            your shelves.
          </h1>

          <p className="mt-5 text-[14px] text-muted-foreground leading-[1.6]">
            MarketPulse only pulls data from the retailers you care about. Pick one to start — you can
            change this any time from Settings.
          </p>

          <div className="mt-10 border-t border-border pt-5 space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] text-muted-foreground">Selected</span>
              <span className="font-mono text-[14px] text-foreground">
                {selected.size.toString().padStart(2, "0")} / {STORES.length}
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] text-muted-foreground">Refresh</span>
              <span className="font-mono text-[12px] text-muted-foreground">every 12 h</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-[12px] text-muted-foreground">History</span>
              <span className="font-mono text-[12px] text-muted-foreground">12 months</span>
            </div>
          </div>
        </div>

        {/* Progress */}
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-0.5 flex-1 bg-primary" />
            <span className="h-0.5 flex-1 bg-border" />
          </div>
          <div className="flex items-center justify-between font-mono text-[11px] text-muted-foreground">
            <span className="text-foreground">Step 01 — Coverage</span>
            <span>Step 02 — Brands</span>
          </div>
        </div>
      </aside>

      {/* ═════════════════ RIGHT — Selection ═════════════════ */}
      <main className="flex flex-col px-6 sm:px-10 lg:px-16 py-8">
        <div className="flex items-center justify-between">
          <div className="flex lg:hidden items-center gap-2">
            <img src={logoImg} alt="MarketPulse" className="h-7 w-auto" />
          </div>
          <p className="lg:hidden text-[11px] font-mono text-muted-foreground">01 / 02</p>
          <button
            onClick={selectAll}
            className="hidden lg:inline-flex text-[12px] text-muted-foreground hover:text-foreground transition-colors"
          >
            Select all
          </button>
        </div>

        <div className="flex-1 flex flex-col justify-center max-w-2xl w-full mx-auto lg:mx-0 py-10">
          <div className="lg:hidden mb-8">
            <h1 className="font-['Inter'] font-semibold text-foreground text-[28px] leading-[1.15] tracking-[-0.01em]">
              Choose your shelves.
            </h1>
            <p className="text-[14px] text-muted-foreground mt-2">
              Pick the retailers you want to monitor.
            </p>
          </div>

          {/* Store list — horizontal rows, not cards */}
          <div className="border border-border rounded-lg bg-surface/40 divide-y divide-border overflow-hidden">
            {STORES.map((store) => {
              const active = selected.has(store.id);
              return (
                <button
                  key={store.id}
                  onClick={() => toggle(store.id)}
                  className={`w-full flex items-center gap-4 px-5 py-4 text-left transition-colors group
                    ${active ? "bg-primary/[0.06]" : "hover:bg-surface-2/60"}`}
                >
                  <div
                    className={`w-11 h-11 rounded-md flex items-center justify-center shrink-0 overflow-hidden border transition-colors
                      ${active ? "bg-surface border-primary/40" : "bg-surface border-border"}`}
                  >
                    <img src={store.logo} alt={store.name} className="w-7 h-7 object-contain" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2.5">
                      <p className="text-[15px] font-medium text-foreground truncate">{store.name}</p>
                      <span className="text-[11px] uppercase tracking-[0.1em] text-muted-foreground font-medium">
                        {store.tag}
                      </span>
                    </div>
                    <p className="text-[12px] font-mono text-muted-foreground mt-0.5">{store.stat}</p>
                  </div>

                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 transition-all border
                      ${active
                        ? "bg-primary border-primary"
                        : "bg-transparent border-border group-hover:border-muted-foreground"}`}
                  >
                    {active && <Check className="w-3 h-3 text-primary-foreground" strokeWidth={3} />}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="flex items-center justify-between mt-8">
            <p className="text-[12px] text-muted-foreground">
              {selected.size === 0 ? (
                <span>Pick at least one to continue.</span>
              ) : (
                <span>
                  <span className="text-foreground font-medium">{selected.size}</span> retailer
                  {selected.size === 1 ? "" : "s"} will be monitored.
                </span>
              )}
            </p>

            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/")}
                className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Cancel
              </button>
              <button
                disabled={selected.size === 0 || loading}
                onClick={handleNext}
                className="inline-flex items-center gap-1.5 bg-foreground text-background rounded-md px-5 py-2.5 text-[14px] font-medium hover:bg-foreground/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? "Saving…" : "Continue"}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground font-mono text-center lg:text-left">
          marketpulse.lv · Preferences saved to your account
        </p>
      </main>
    </div>
  );
}
