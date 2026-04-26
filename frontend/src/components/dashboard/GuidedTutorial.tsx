import { useState, useEffect, useCallback, useRef } from "react";

const STEPS = [
  {
    target: "[data-tutorial='search']",
    title: "Search",
    desc: "Search any perfume — we'll show prices from all your tracked stores.",
  },
  {
    target: "[data-tutorial='filters']",
    title: "Store filters",
    desc: "Quickly switch between retailers or see the full market at once.",
  },
  {
    target: "[data-tutorial='feed']",
    title: "Price feed",
    desc: "Latest movements for your brands. A down arrow means the price dropped.",
  },
  {
    target: "[data-tutorial='product-card']",
    title: "Product card",
    desc: "Click any card to open the full price history chart.",
  },
  {
    target: "[data-tutorial='ai-panel']",
    title: "AI assistant",
    desc: "Ask anything: 'What's the cheapest Hugo Boss right now?'",
  },
  {
    target: "[data-tutorial='account']",
    title: "Account",
    desc: "Manage notifications, theme, and profile here.",
  },
];

type Rect = { top: number; left: number; width: number; height: number };

export default function GuidedTutorial({
  onComplete,
  onStepChange,
}: {
  onComplete: () => void;
  onStepChange?: (stepIndex: number) => void;
}) {
  const [step, setStep] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const isLastStep = step >= STEPS.length;

  const measureTarget = useCallback((stepIdx: number) => {
    if (stepIdx >= STEPS.length) {
      setTargetRect(null);
      return;
    }
    const el = document.querySelector(STEPS[stepIdx].target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const pad = 8;
    setTargetRect({
      top: r.top - pad,
      left: r.left - pad,
      width: r.width + pad * 2,
      height: r.height + pad * 2,
    });
  }, []);

  useEffect(() => {
    onStepChange?.(step);
    measureTarget(step);
    const timer = setTimeout(() => measureTarget(step), 350);
    const onResize = () => measureTarget(step);
    window.addEventListener("resize", onResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", onResize);
    };
  }, [step, measureTarget, onStepChange]);

  const handleNext = () => {
    if (isLastStep) {
      onComplete();
      return;
    }
    setStep((s) => s + 1);
  };

  // Tooltip: anchor below target, fall back above if too close to bottom
  const tooltipStyle = (): React.CSSProperties => {
    const W = 256;
    const H = 148;
    const pad = 16;

    if (isLastStep || !targetRect) {
      return {
        left: window.innerWidth / 2 - W / 2,
        top: window.innerHeight / 2 - H / 2,
      };
    }

    let x = targetRect.left + targetRect.width / 2 - W / 2;
    let y = targetRect.top + targetRect.height + 16;

    if (y + H > window.innerHeight - pad) y = targetRect.top - H - 16;
    if (y < pad) y = pad;
    if (x + W > window.innerWidth - pad) x = window.innerWidth - W - pad;
    if (x < pad) x = pad;

    return { left: x, top: y };
  };

  return (
    <div ref={overlayRef} className="fixed inset-0 z-[10000]" style={{ pointerEvents: "auto" }}>
      {/* Overlay with spotlight cutout */}
      <svg
        className="absolute inset-0 w-full h-full"
        style={{ pointerEvents: "none" }}
      >
        <defs>
          <mask id="tutorial-mask">
            <rect width="100%" height="100%" fill="white" />
            {targetRect && (
              <rect
                x={targetRect.left}
                y={targetRect.top}
                width={targetRect.width}
                height={targetRect.height}
                rx="8"
                fill="black"
                style={{ transition: "all 0.4s cubic-bezier(0.4,0,0.2,1)" }}
              />
            )}
          </mask>
        </defs>

        <rect
          width="100%"
          height="100%"
          fill="rgba(0,0,0,0.55)"
          mask="url(#tutorial-mask)"
        />

        {/* Target outline */}
        {targetRect && (
          <rect
            x={targetRect.left}
            y={targetRect.top}
            width={targetRect.width}
            height={targetRect.height}
            rx="8"
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="1.5"
            opacity="0.9"
            style={{ transition: "all 0.4s cubic-bezier(0.4,0,0.2,1)" }}
          />
        )}
      </svg>

      {/* Tooltip */}
      <div
        className="absolute z-[10001] w-[256px] bg-background border border-border rounded-md shadow-[0_8px_32px_rgba(0,0,0,0.5)] flex flex-col gap-3 p-4"
        style={{
          ...tooltipStyle(),
          transition: "all 0.4s cubic-bezier(0.4,0,0.2,1)",
        }}
      >
        {isLastStep ? (
          <div className="flex flex-col gap-3 py-1">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                All done
              </span>
              <p className="font-['Inter'] font-semibold text-foreground text-[15px] tracking-[-0.005em]">
                You're all set.
              </p>
              <p className="text-[12.5px] text-muted-foreground leading-relaxed">
                Start exploring prices and finding the best deals.
              </p>
            </div>
            <button
              onClick={handleNext}
              className="w-full h-9 rounded-md bg-foreground text-background text-[12.5px] font-medium hover:bg-foreground/90 transition-colors"
            >
              Start exploring
            </button>
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  {STEPS[step].title}
                </span>
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
                  {String(step + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}
                </span>
              </div>
              <p className="text-[12.5px] text-foreground leading-relaxed">
                {STEPS[step].desc}
              </p>
            </div>

            {/* Progress bar */}
            <div className="h-[2px] w-full bg-surface-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
              />
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={onComplete}
                className="text-[11.5px] text-muted-foreground hover:text-foreground transition-colors"
              >
                Skip
              </button>
              <button
                onClick={handleNext}
                className="h-7 px-3 rounded bg-foreground text-background text-[11.5px] font-medium hover:bg-foreground/90 transition-colors inline-flex items-center gap-1"
              >
                Next
                <span className="text-[9px]">→</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
