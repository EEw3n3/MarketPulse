import { useState, useEffect, useRef } from "react";
import { ArrowLeft, Check, Plus, Search, X, Loader2 } from "lucide-react";

const BRANDS = [
  "Dior", "Chanel", "Tom Ford", "Versace", "Hugo Boss", "Armani",
  "Paco Rabanne", "Jean Paul Gaultier", "Creed", "Maison Margiela",
  "YSL", "Burberry", "Dolce & Gabbana", "Guerlain", "Givenchy",
  "Lacoste", "Calvin Klein", "Hermès", "Davidoff", "Montblanc",
  "Armaf", "Mancera", "Afnan", "Lattafa", "Rasasi",
  "Attar Collection", "Parfums de Marly", "Initio", "Memo Paris", "Xerjoff",
];

const KNOWN_OTHER_BRANDS = ["Byredo", "Acqua di Parma", "Narciso Rodriguez", "Penhaligon's", "Amouage"];

interface OnboardingStep2Props {
  open: boolean;
  onClose: () => void;
  onBack: () => void;
}

const OnboardingStep2 = ({ open, onClose, onBack }: OnboardingStep2Props) => {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [showOtherInput, setShowOtherInput] = useState(false);
  const [otherQuery, setOtherQuery] = useState("");
  const [otherStatus, setOtherStatus] = useState<"idle" | "checking" | "found" | "not-found">("idle");
  const otherInputRef = useRef<HTMLInputElement>(null);

  const toggle = (brand: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(brand) ? next.delete(brand) : next.add(brand);
      return next;
    });
  };

  const filtered = BRANDS.filter((b) => b.toLowerCase().includes(search.toLowerCase()));

  /* Simulate DB check for custom brand */
  useEffect(() => {
    if (!otherQuery.trim()) { setOtherStatus("idle"); return; }
    setOtherStatus("checking");
    const t = setTimeout(() => {
      const found = KNOWN_OTHER_BRANDS.some((b) => b.toLowerCase() === otherQuery.trim().toLowerCase());
      setOtherStatus(found ? "found" : "not-found");
    }, 500);
    return () => clearTimeout(t);
  }, [otherQuery]);

  const addOtherBrand = () => {
    if (otherStatus === "found") {
      const match = KNOWN_OTHER_BRANDS.find((b) => b.toLowerCase() === otherQuery.trim().toLowerCase());
      if (match) {
        setSelected((prev) => new Set(prev).add(match));
        setOtherQuery("");
        setShowOtherInput(false);
      }
    }
  };

  useEffect(() => {
    if (showOtherInput) otherInputRef.current?.focus();
  }, [showOtherInput]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center px-4 animate-fade-in"
      style={{ backdropFilter: "blur(14px)", background: "rgba(0,0,0,0.75)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="relative w-full max-w-[640px] rounded-modal animate-scale-in"
        style={{
          background: "hsl(var(--surface))",
          border: "1px solid hsl(var(--border))",
          boxShadow: "0 32px 80px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05)",
          padding: "40px",
        }}
      >
        {/* Top Progress Bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-surface-2 overflow-hidden rounded-t-modal">
          <div className="h-full w-full bg-primary transition-all duration-500 ease-brand shadow-[0_0_12px_rgba(124,58,237,0.6)]" />
        </div>
        {/* Close */}
        <button onClick={onClose} className="absolute top-5 right-5 text-muted-foreground hover:text-foreground transition-colors">
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <h2 className="font-display text-2xl font-bold text-foreground mb-1.5">
          Which brands interest you?
        </h2>
        <p className="text-[13px] text-muted-foreground mb-5">
          Personalize your feed based on your taste.
        </p>

        {/* Search */}
        <div className="relative mb-5">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search brand..."
            className="w-full h-10 pl-9 pr-4 rounded-card border border-border bg-surface-2/50 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/40 transition-all"
          />
        </div>

        {/* Brand pills */}
        <div className="flex flex-wrap gap-2 mb-6 max-h-[240px] overflow-y-auto pr-1">
          {filtered.map((brand) => {
            const isSelected = selected.has(brand);
            return (
              <button
                key={brand}
                onClick={() => toggle(brand)}
                className={`
                  inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium
                  border transition-all duration-200 ease-brand
                  ${isSelected
                    ? "bg-primary text-primary-foreground border-primary shadow-[0_0_16px_rgba(124,58,237,0.35)]"
                    : "border-border/50 bg-surface-2/40 text-muted-foreground hover:border-primary/40 hover:bg-surface-2 hover:text-foreground"
                  }
                `}
              >
                {isSelected && <Check className="w-3 h-3" />}
                {brand}
              </button>
            );
          })}

          {/* + Other Brand pill */}
          {!showOtherInput && (
            <button
              onClick={() => setShowOtherInput(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium border border-dashed border-border text-muted-foreground hover:border-primary/40 hover:text-foreground transition-all duration-200"
            >
              <Plus className="w-3 h-3" /> Other Brand
            </button>
          )}
        </div>

        {/* Other brand input */}
        {showOtherInput && (
          <div className="mb-6 flex items-center gap-3">
            <div className="relative flex-1">
              <input
                ref={otherInputRef}
                type="text"
                value={otherQuery}
                onChange={(e) => setOtherQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addOtherBrand()}
                placeholder="Type a brand name..."
                className="w-full h-9 px-3 rounded-card border border-border bg-surface-2/50 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/40 transition-all"
              />
            </div>
            {otherStatus === "checking" && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Checking…
              </span>
            )}
            {otherStatus === "found" && (
              <button onClick={addOtherBrand} className="flex items-center gap-1 text-xs text-success font-medium whitespace-nowrap">
                <Check className="w-3.5 h-3.5" /> Found in database
              </button>
            )}
            {otherStatus === "not-found" && (
              <span className="text-xs text-muted-foreground whitespace-nowrap">Brand not found yet</span>
            )}
            <button onClick={() => { setShowOtherInput(false); setOtherQuery(""); }} className="text-muted-foreground hover:text-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between">
          <div className="flex-1" />

          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="inline-flex items-center text-sm font-medium border border-primary text-primary rounded-button px-5 py-2.5 transition-all ease-brand hover:bg-primary/10"
            >
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <button
              onClick={() => selected.size > 0 && onClose()}
              disabled={selected.size === 0}
              className={`
                btn-primary text-sm px-6 py-2.5 transition-all duration-200
                ${selected.size === 0 ? "opacity-40 cursor-not-allowed !shadow-none" : "hover:scale-[1.03]"}
              `}
            >
              Let's Go!
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OnboardingStep2;
