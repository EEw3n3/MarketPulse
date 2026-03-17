import { useState, useEffect, useCallback, useRef } from "react";
import { MousePointer2 } from "lucide-react";

const STEPS = [
  {
    target: "[data-tutorial='search']",
    title: "Search Bar",
    desc: "Search any perfume — we'll show prices from all your tracked stores.",
  },
  {
    target: "[data-tutorial='filters']",
    title: "Store Filters",
    desc: "Quickly switch between stores or see all at once.",
  },
  {
    target: "[data-tutorial='feed']",
    title: "Product Feed",
    desc: "Latest price changes for your brands. Green arrow = price dropped!",
  },
  {
    target: "[data-tutorial='product-card']",
    title: "Product Card",
    desc: "Click any card to see the full price history chart.",
  },
  {
    target: "[data-tutorial='ai-panel']",
    title: "AI Assistant",
    desc: "Ask anything: 'What's the cheapest Hugo Boss right now?'",
  },
  {
    target: "[data-tutorial='account']",
    title: "Account Menu",
    desc: "Manage notifications, theme, and profile here.",
  },
];

function ConfettiBurst() {
  const particles = Array.from({ length: 40 }, (_, i) => {
    const angle = (Math.PI * 2 * i) / 40 + Math.random() * 0.3;
    const dist = 80 + Math.random() * 120;
    const size = 4 + Math.random() * 6;
    const colors = [
      "hsl(263,70%,58%)",
      "hsl(160,84%,39%)",
      "hsl(187,94%,43%)",
      "hsl(45,100%,60%)",
      "hsl(0,84%,60%)",
    ];
    return {
      id: i,
      x: Math.cos(angle) * dist,
      y: Math.sin(angle) * dist - 40,
      size,
      color: colors[i % colors.length],
      rotation: Math.random() * 360,
      delay: Math.random() * 0.15,
    };
  });

  return (
    <div className="fixed inset-0 z-[10001] pointer-events-none flex items-center justify-center">
      {particles.map((p) => (
        <span
          key={p.id}
          className="absolute rounded-sm"
          style={{
            width: p.size,
            height: p.size,
            backgroundColor: p.color,
            transform: `rotate(${p.rotation}deg)`,
            animation: `confetti-fly 0.8s ${p.delay}s cubic-bezier(0.25,0.46,0.45,0.94) forwards`,
            ["--cx" as string]: `${p.x}px`,
            ["--cy" as string]: `${p.y}px`,
            opacity: 1,
          }}
        />
      ))}
      <style>{`
        @keyframes confetti-fly {
          0% { transform: translate(0,0) rotate(0deg) scale(1); opacity: 1; }
          100% { transform: translate(var(--cx), var(--cy)) rotate(720deg) scale(0); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

type Rect = { top: number; left: number; width: number; height: number };

export default function GuidedTutorial({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [showConfetti, setShowConfetti] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  const isLastStep = step >= STEPS.length;

  const measureTarget = useCallback((stepIdx: number) => {
    if (stepIdx >= STEPS.length) {
      setTargetRect(null);
      setCursorPos({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
      return;
    }
    const el = document.querySelector(STEPS[stepIdx].target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const pad = 8;
    const rect = {
      top: r.top - pad,
      left: r.left - pad,
      width: r.width + pad * 2,
      height: r.height + pad * 2,
    };
    setTargetRect(rect);
    setCursorPos({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height + 12,
    });
  }, []);

  useEffect(() => {
    measureTarget(step);
    const onResize = () => measureTarget(step);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [step, measureTarget]);

  const handleNext = () => {
    if (isLastStep) {
      setShowConfetti(true);
      setTimeout(() => onComplete(), 900);
      return;
    }
    setStep((s) => s + 1);
  };

  // Tooltip positioning: try right of cursor, fall back left
  const tooltipStyle = (): React.CSSProperties => {
    const tooltipW = 260;
    const tooltipH = 160;
    let x = cursorPos.x + 32;
    let y = cursorPos.y - 20;
    if (x + tooltipW > window.innerWidth - 20) x = cursorPos.x - tooltipW - 32;
    if (y + tooltipH > window.innerHeight - 20) y = window.innerHeight - tooltipH - 20;
    if (y < 20) y = 20;
    if (isLastStep) {
      x = window.innerWidth / 2 - tooltipW / 2;
      y = window.innerHeight / 2 - tooltipH / 2;
    }
    return { left: x, top: y };
  };

  return (
    <>
      {showConfetti && <ConfettiBurst />}

      <div ref={overlayRef} className="fixed inset-0 z-[10000]" style={{ pointerEvents: "auto" }}>
        {/* Dark overlay with spotlight cutout via SVG */}
        <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: "none" }}>
          <defs>
            <mask id="tutorial-mask">
              <rect width="100%" height="100%" fill="white" />
              {targetRect && (
                <rect
                  x={targetRect.left}
                  y={targetRect.top}
                  width={targetRect.width}
                  height={targetRect.height}
                  rx="12"
                  fill="black"
                  style={{
                    transition: "all 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
                  }}
                />
              )}
            </mask>
          </defs>
          {/* Spotlight pulse ring */}
          {targetRect && (
            <rect
              x={targetRect.left - 4}
              y={targetRect.top - 4}
              width={targetRect.width + 8}
              height={targetRect.height + 8}
              rx="16"
              fill="none"
              stroke="hsl(263, 70%, 58%)"
              strokeWidth="2"
              opacity="0.5"
              className="animate-spotlight-pulse"
              style={{
                transition: "all 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
                transformOrigin: `${targetRect.left + targetRect.width / 2}px ${targetRect.top + targetRect.height / 2}px`,
              }}
            />
          )}
          <rect
            width="100%"
            height="100%"
            fill="rgba(0,0,0,0.6)"
            mask="url(#tutorial-mask)"
          />
        </svg>

        {/* Animated cursor */}
        {!isLastStep && (
          <div
            className="absolute z-[10001] pointer-events-none"
            style={{
              left: cursorPos.x,
              top: cursorPos.y,
              transition: "all 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
              transform: "translate(-50%, -50%)",
            }}
          >
            <MousePointer2
              size={48}
              className="text-primary drop-shadow-[0_0_16px_rgba(124,58,237,0.6)]"
              style={{ opacity: 0.8 }}
            />
          </div>
        )}

        {/* Tooltip */}
        <div
          className="absolute z-[10002] w-[260px] bg-[rgba(255,255,255,0.06)] backdrop-blur-[20px] border border-[rgba(255,255,255,0.1)] rounded-2xl p-4 flex flex-col gap-3 shadow-[0_16px_48px_rgba(0,0,0,0.5)]"
          style={{
            ...tooltipStyle(),
            transition: "all 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          {isLastStep ? (
            <div className="flex flex-col items-center gap-4 py-4">
              <p className="text-foreground text-lg font-bold font-['Outfit',sans-serif] text-center">
                You're all set! 🎉
              </p>
              <p className="text-muted-foreground text-[13px] text-center">
                Start exploring prices and finding the best deals.
              </p>
              <button
                onClick={handleNext}
                className="px-8 py-2.5 rounded-full bg-[hsl(var(--success))] text-[hsl(var(--success-foreground))] font-bold text-sm hover:brightness-110 transition shadow-[0_0_24px_rgba(16,185,129,0.4)]"
              >
                Start!
              </button>
            </div>
          ) : (
            <>
              <div>
                <p className="text-foreground text-sm font-bold">{STEPS[step].title}</p>
                <p className="text-muted-foreground text-[13px] leading-relaxed mt-1">
                  {STEPS[step].desc}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground text-[12px]">
                  {step + 1} / {STEPS.length}
                </span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={onComplete}
                    className="text-muted-foreground text-[12px] hover:text-foreground transition-colors"
                  >
                    Skip
                  </button>
                  <button
                    onClick={handleNext}
                    className="px-4 py-1.5 rounded-full bg-primary text-primary-foreground text-[13px] font-semibold hover:brightness-110 transition"
                  >
                    Next →
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
