import { useState, useEffect } from "react";
import { Check, ChevronRight, X } from "lucide-react";

import storeDouglas from "@/assets/store-douglas.png";
import storeNotino from "@/assets/store-notino.png";
import store220 from "@/assets/store-220.png";
import storeMakeup from "@/assets/store-makeup.png";
import store1a from "@/assets/store-1a.png";

/* ── Store data ───────────────────────────────────────────────── */
const stores = [
  { id: "douglas", name: "Douglas.lv", stat: "273 products", logo: storeDouglas },
  { id: "notino", name: "Notino.lv", stat: "1 000+ listings", logo: storeNotino },
  { id: "220", name: "220.lv", stat: "540 products", logo: store220 },
  { id: "makeup", name: "Makeup.lv", stat: "890 products", logo: storeMakeup },
  { id: "1a", name: "1a.lv", stat: "320 products", logo: store1a },
];

/* ── Component ────────────────────────────────────────────────── */
interface OnboardingModalProps {
  open: boolean;
  onClose: () => void;
  onNext?: () => void;
}

const OnboardingModal = ({ open, onClose, onNext }: OnboardingModalProps) => {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [justAdded, setJustAdded] = useState<string | null>(null);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        setJustAdded(null);
      } else {
        next.add(id);
        setJustAdded(id);
      }
      return next;
    });
  };

  /* Clear pop animation flag */
  useEffect(() => {
    if (!justAdded) return;
    const t = setTimeout(() => setJustAdded(null), 350);
    return () => clearTimeout(t);
  }, [justAdded]);

  /* Escape to close */
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
        className="relative w-full max-w-[580px] rounded-modal animate-scale-in"
        style={{
          background: "hsl(var(--surface))",
          border: "1px solid hsl(var(--border))",
          boxShadow: "0 32px 80px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05)",
          padding: "40px",
        }}
      >
        {/* Top Progress Bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-surface-2 overflow-hidden rounded-t-modal">
          <div className="h-full w-1/2 bg-primary transition-all duration-500 ease-brand shadow-[0_0_12px_rgba(124,58,237,0.6)]" />
        </div>
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <h2 className="font-display text-2xl font-bold text-foreground mb-1.5">
          Which stores would you like to track?
        </h2>
        <p className="text-[13px] text-muted-foreground mb-7">
          Choose stores — we'll only show prices that matter to you.
        </p>

        {/* Store grid: 2+2+1 */}
        <div className="grid grid-cols-2 gap-3 mb-8">
          {stores.map((store) => {
            const isSelected = selected.has(store.id);
            const isPopping = justAdded === store.id;

            return (
              <button
                key={store.id}
                onClick={() => toggle(store.id)}
                className={`
                  relative flex items-center gap-3 p-4 rounded-card border text-left
                  transition-all duration-200 ease-brand group
                  ${
                    isSelected
                      ? "border-primary bg-primary/[0.08] shadow-[0_0_20px_rgba(124,58,237,0.15)] ring-1 ring-primary"
                      : "border-border/60 bg-surface-2/30 hover:bg-surface-2 hover:border-primary/50 hover:shadow-[0_4px_16px_rgba(124,58,237,0.1)]"
                  }
                  ${store.id === "1a" ? "col-span-2 sm:col-span-1 sm:col-start-1" : ""}
                `}
              >
                {/* Logo */}
                <div
                  className={`
                    w-11 h-11 rounded-lg flex items-center justify-center shrink-0 overflow-hidden
                    transition-colors duration-200
                    ${isSelected ? "bg-primary/20" : "bg-surface-2"}
                  `}
                >
                  <img
                    src={store.logo}
                    alt={store.name}
                    className="w-7 h-7 object-contain opacity-90"
                  />
                </div>

                {/* Text */}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground truncate">{store.name}</p>
                  <p className="text-[11px] text-muted-foreground">{store.stat}</p>
                </div>

                {/* Check badge */}
                <div
                  className={`
                    absolute top-2.5 right-2.5 w-5 h-5 rounded-full flex items-center justify-center
                    transition-all duration-200
                    ${
                      isSelected
                        ? `bg-primary scale-100 opacity-100 ${isPopping ? "animate-[pop_0.3s_ease-out]" : ""}`
                        : "bg-transparent scale-75 opacity-0"
                    }
                  `}
                >
                  <Check className="w-3 h-3 text-primary-foreground" />
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex justify-end">

          {/* Next button */}
          <button
            disabled={selected.size === 0}
            onClick={onNext}
            className={`
              btn-primary text-sm px-6 py-2.5 transition-all duration-200
              ${selected.size === 0 ? "opacity-40 cursor-not-allowed !shadow-none" : "hover:scale-[1.03]"}
            `}
          >
            Next <ChevronRight className="w-4 h-4 ml-1 inline" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default OnboardingModal;
