import { useNavigate } from "react-router-dom";
import logoImg from "@/assets/logo.png";
import {
  ArrowDown,
  ArrowUpRight,
  Bell,
  Bot,
  Database,
  FileText,
  LineChart,
  Lock,
  Radio,
  Package,
} from "lucide-react";
import { useReveal } from "@/hooks/use-reveal";
import { useCountUp } from "@/hooks/use-count-up";
import { useTypewriter } from "@/hooks/use-typewriter";
import Reveal from "@/components/analytics/Reveal";

/* ─────────────────────────────────────────────────────────────────
 *  MarketPulse — Landing page
 *  Editorial dark navy + teal. Each section has its own visual
 *  dominant (timeline / bento / mini-vis / typewriter / code mock)
 *  while sharing the same typography and grid rhythm.
 *  Moderate scroll-anchored animations (Stripe / Vercel level).
 * ───────────────────────────────────────────────────────────────── */

const STORES = [
  { name: "Douglas", domain: "douglas.lv" },
  { name: "Notino", domain: "notino.lv" },
  { name: "Makeup", domain: "makeup.lv" },
  { name: "1A", domain: "1a.lv" },
  { name: "220", domain: "220.lv" },
];

const PILLARS = [
  {
    icon: Database,
    title: "Source-of-truth data",
    desc: "Twice-daily scans against the live retailer pages — not feeds, not estimates. What the customer sees is what we record.",
  },
  {
    icon: LineChart,
    title: "Historical depth",
    desc: "Every price point is kept indefinitely. Query twelve months of movement on any SKU without stitching exports.",
  },
  {
    icon: Bot,
    title: "Conversational analysis",
    desc: "Ask questions in plain English. The assistant queries your monitored set and returns the numbers, not opinions.",
  },
  {
    icon: Bell,
    title: "Precision alerts",
    desc: "Threshold-based, noise-free. No daily digest spam — only the drops that cross the filter you defined.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Select retailers and brands",
    desc: "Pick the stores and brands relevant to your workflow. Coverage updates nightly.",
  },
  {
    n: "02",
    title: "Define alert thresholds",
    desc: "Set percentage drops, absolute price targets, or leave defaults. Route to email or Telegram.",
  },
  {
    n: "03",
    title: "Export and analyse",
    desc: "Pull any monitored window as CSV, Excel, JSON or PDF. Share history without leaking your config.",
  },
];

const SAMPLE_OFFERS = [
  { tag: "NO", store: "Notino.lv", price: 92.4, fillPct: 0 },
  { tag: "DO", store: "Douglas.lv", price: 99.0, fillPct: 22 },
  { tag: "MA", store: "Makeup.lv", price: 102.5, fillPct: 33 },
  { tag: "1A", store: "1a.lv", price: 108.9, fillPct: 55 },
  { tag: "22", store: "220.lv", price: 115.0, fillPct: 75 },
];

/* ─────────────────────────────────────────────────────────────────
 *  Mini visual primitives — each Stats cell gets its own
 * ───────────────────────────────────────────────────────────────── */

function Dots({ count }: { count: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {[...Array(count)].map((_, i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-primary"
          style={{ opacity: 0.4 + (i / count) * 0.6 }}
        />
      ))}
    </div>
  );
}

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="relative w-full max-w-[120px] h-1 rounded-full bg-border overflow-hidden">
      <div
        className="h-full bg-primary rounded-full transition-[width] duration-1000 ease-out"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

function Sparkline({ points }: { points: number[] }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const w = 110;
  const h = 22;
  const step = w / (points.length - 1);
  const path = points
    .map((p, i) => {
      const x = i * step;
      const y = h - ((p - min) / range) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={path} fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={(points.length - 1) * step} cy={h - ((points[points.length - 1] - min) / range) * h} r="2.5" fill="hsl(var(--primary))" />
    </svg>
  );
}

function Ring({ segments }: { segments: number }) {
  const size = 24;
  const cx = size / 2;
  const cy = size / 2;
  const r = 9;
  return (
    <svg width={size} height={size} className="overflow-visible">
      {[...Array(segments)].map((_, i) => {
        const a1 = (i / segments) * Math.PI * 2 - Math.PI / 2;
        const a2 = ((i + 0.85) / segments) * Math.PI * 2 - Math.PI / 2;
        const x1 = cx + r * Math.cos(a1);
        const y1 = cy + r * Math.sin(a1);
        const x2 = cx + r * Math.cos(a2);
        const y2 = cy + r * Math.sin(a2);
        return (
          <path
            key={i}
            d={`M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`}
            stroke="hsl(var(--primary))"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
            opacity={0.45 + (i / segments) * 0.55}
          />
        );
      })}
    </svg>
  );
}

/* Corner accents for Pillars (different per variant) */
function CornerSparkline() {
  return (
    <svg width="44" height="20" className="overflow-visible">
      <path d="M0 14 L10 10 L20 12 L30 6 L44 2" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function CornerTypingDots() {
  return (
    <div className="flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1 h-1 rounded-full bg-primary animate-typing-dot"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function CornerPing() {
  return (
    <span className="relative flex w-2 h-2">
      <span className="absolute inline-flex w-full h-full rounded-full bg-primary opacity-60 animate-ping" />
      <span className="relative inline-flex w-2 h-2 rounded-full bg-primary" />
    </span>
  );
}

function DotMatrix() {
  return (
    <svg width="180" height="180" className="text-primary">
      {[...Array(10)].map((_, row) =>
        [...Array(10)].map((__, col) => (
          <circle key={`${row}-${col}`} cx={col * 18 + 4} cy={row * 18 + 4} r="1.4" fill="currentColor" />
        ))
      )}
    </svg>
  );
}

function PdfMockup() {
  return (
    <div className="bg-surface-2 rounded-md p-3 space-y-1.5">
      <div className="flex items-center justify-between mb-1.5">
        <span className="font-mono text-[8px] uppercase tracking-[0.14em] text-muted-foreground">PDF · 1/4</span>
        <span className="font-mono text-[8px] text-primary">Apr 2026</span>
      </div>
      <div className="h-1 w-3/4 bg-foreground/30 rounded-sm" />
      <div className="h-1 w-1/2 bg-muted-foreground/30 rounded-sm" />
      <div className="flex items-end gap-0.5 h-8 mt-2">
        {[40, 60, 35, 75, 55, 85, 50].map((h, i) => (
          <div key={i} className="flex-1 bg-primary/40 rounded-t-sm" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
 *  Stats band — KPI cells with mini-vis
 * ───────────────────────────────────────────────────────────────── */

function StatCell({
  value,
  label,
  viz,
  trigger,
}: {
  value: string;
  label: string;
  viz: React.ReactNode;
  trigger: boolean;
}) {
  const animated = useCountUp(value, 1400, trigger);
  return (
    <div className="bg-background px-7 py-10 md:py-14 relative">
      <p className="font-display font-semibold text-foreground text-[44px] md:text-[64px] leading-none tracking-[-0.04em] tabular-nums">
        {animated}
      </p>
      <div className="mt-5 mb-5 h-6 flex items-center">{viz}</div>
      <p className="text-[12px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
        {label}
      </p>
    </div>
  );
}

function StatsBand() {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-card overflow-hidden border border-border"
    >
      <StatCell value="5" label="Retailers covered" viz={<Dots count={5} />} trigger={revealed} />
      <StatCell value="1,200+" label="SKUs monitored" viz={<ProgressBar percent={revealed ? 68 : 0} />} trigger={revealed} />
      <StatCell value="4,800+" label="Price checks / day" viz={<Sparkline points={[3, 5, 4, 6, 5, 7, 6, 8]} />} trigger={revealed} />
      <StatCell value="12" label="Months retained" viz={<Ring segments={12} />} trigger={revealed} />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
 *  Animated price timeline chart — Section A
 * ───────────────────────────────────────────────────────────────── */

const PriceTimelineChart = () => {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  const lines = [
    { store: "Douglas", color: "hsl(217, 91%, 60%)", d: "M0 60 L50 55 L100 58 L150 50 L200 44 L250 40 L300 36 L350 35" },
    { store: "Notino", color: "hsl(var(--primary))", d: "M0 70 L50 65 L100 60 L150 58 L200 50 L250 46 L300 42 L350 38" },
    { store: "Makeup", color: "hsl(330, 70%, 55%)", d: "M0 80 L50 78 L100 72 L150 70 L200 66 L250 62 L300 58 L350 56" },
    { store: "1a.lv", color: "hsl(25, 85%, 55%)", d: "M0 90 L50 92 L100 88 L150 90 L200 86 L250 85 L300 82 L350 80" },
    { store: "220.lv", color: "hsl(45, 80%, 55%)", d: "M0 100 L50 102 L100 98 L150 100 L200 96 L250 94 L300 92 L350 90" },
  ];

  return (
    <div ref={ref} className="bg-surface border border-border rounded-card overflow-hidden shadow-[0_24px_48px_-24px_rgba(0,0,0,0.5)]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-medium">Tracked SKU</p>
          <p className="text-sm font-semibold text-foreground mt-0.5">Dior Sauvage EDP 100 ml</p>
        </div>
        <div className="flex items-center gap-1 bg-surface-2 border border-border rounded-md p-0.5">
          {["30D", "90D", "1Y"].map((p) => (
            <span
              key={p}
              className={`px-2.5 py-1 rounded text-[11px] font-medium ${p === "90D" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
            >
              {p}
            </span>
          ))}
        </div>
      </div>

      {/* Chart body */}
      <div className="p-5">
        <svg viewBox="0 0 380 140" className="w-full h-auto">
          {[20, 50, 80, 110].map((y) => (
            <line key={y} x1="0" y1={y} x2="380" y2={y} stroke="hsl(var(--border))" strokeWidth="1" strokeDasharray="2 3" />
          ))}
          <text x="360" y="24" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">145 €</text>
          <text x="360" y="54" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">135 €</text>
          <text x="360" y="84" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">125 €</text>
          <text x="360" y="114" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">115 €</text>

          {lines.map((l, idx) => (
            <path
              key={l.store}
              d={l.d}
              stroke={l.color}
              strokeWidth="1.8"
              fill="none"
              strokeLinecap="round"
              strokeDasharray="600"
              strokeDashoffset={revealed ? 0 : 600}
              style={{ transition: `stroke-dashoffset 1.4s cubic-bezier(0.22, 1, 0.36, 1) ${idx * 120}ms` }}
            />
          ))}

          {/* Highlight point — Douglas drop */}
          <circle cx="300" cy="36" r="4" fill="hsl(var(--success))" opacity={revealed ? 1 : 0} style={{ transition: "opacity 0.4s ease-out 1.6s" }} />
          <circle cx="300" cy="36" r="9" fill="hsl(var(--success))" fillOpacity={revealed ? 0.18 : 0} className={revealed ? "animate-pulse-ring" : ""} style={{ transformOrigin: "300px 36px" }} />
        </svg>

        <div className="flex justify-between mt-2 text-[10px] text-muted-foreground tabular-nums font-mono">
          <span>Dec</span>
          <span>Jan</span>
          <span>Feb</span>
          <span>Mar</span>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-4 pt-4 border-t border-border">
          {lines.map((l) => (
            <span key={l.store} className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: l.color }} />
              {l.store}
            </span>
          ))}
        </div>
      </div>

      {/* Annotation strip */}
      <div
        className="flex items-center justify-between px-5 py-3 border-t border-border bg-surface-2/40 text-[11px] transition-all duration-700 ease-out"
        style={{
          opacity: revealed ? 1 : 0,
          transform: revealed ? "translateY(0)" : "translateY(8px)",
          transitionDelay: "1.7s",
        }}
      >
        <span className="text-muted-foreground">
          Mar 14 · Douglas dropped to <span className="text-foreground font-semibold tabular-nums">125.00 €</span>
        </span>
        <span className="inline-flex items-center gap-1 text-success font-semibold tabular-nums">
          <ArrowDown className="w-3 h-3" />
          7.4% vs. 30-day avg
        </span>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────
 *  AI Transcript with typewriter — Section D
 * ───────────────────────────────────────────────────────────────── */

const AiTranscript = () => {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  const reply =
    "Hugo Boss Bottled EDP 100 ml at 62.90 € on Notino — its lowest in 3 months. Douglas is 68.50 € (+8.9%) and 1a.lv is out of stock.";
  const { text, done } = useTypewriter(reply, 16, revealed);

  return (
    <div ref={ref} className="bg-surface border border-border rounded-card overflow-hidden shadow-[0_24px_48px_-24px_rgba(0,0,0,0.5)]">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-border">
        <Bot className="w-4 h-4 text-primary" />
        <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
          MarketPulse assistant
        </span>
      </div>
      <div className="p-5 space-y-4">
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">You</p>
          <p className="text-sm text-foreground">Which Hugo Boss EDP is cheapest right now across my monitored stores?</p>
        </div>
        <div className="border-l-2 border-primary pl-4">
          <p className="text-[10px] text-primary uppercase tracking-wide mb-1 font-medium">Assistant</p>
          <p className="text-sm text-foreground leading-relaxed min-h-[48px]">
            {text}
            {revealed && !done && (
              <span className="inline-block w-[6px] h-[14px] bg-foreground ml-0.5 align-middle animate-typing-cursor" />
            )}
          </p>
          {done && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 animate-fade-in">
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mr-1">Sources</span>
              {["notino.lv", "douglas.lv", "1a.lv"].map((s) => (
                <span
                  key={s}
                  className="font-mono text-[10px] text-muted-foreground border border-border rounded px-1.5 py-0.5 hover:text-foreground hover:border-primary/40 transition-colors cursor-default"
                >
                  {s} ↗
                </span>
              ))}
            </div>
          )}
          <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="w-1 h-1 rounded-full bg-primary" />
            Based on 247 price points · queried in 0.8s
          </div>
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────
 *  Sample SKU showcase — Section between Stats and Workflow
 * ───────────────────────────────────────────────────────────────── */

const SampleSku = () => {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} className="grid md:grid-cols-[0.9fr_1.1fr] gap-px bg-border rounded-card overflow-hidden border border-border">
      {/* Product card */}
      <div className="bg-background p-8 flex flex-col">
        <div className="aspect-square bg-surface-2/60 border border-border rounded-md mb-6 flex items-center justify-center relative overflow-hidden">
          <div
            aria-hidden
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage: "radial-gradient(circle at 50% 30%, hsl(var(--primary) / 0.4), transparent 60%)",
            }}
          />
          <Package className="w-20 h-20 text-muted-foreground/30 relative" strokeWidth={1.25} />
        </div>
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-1.5">Dior</p>
        <h3 className="font-display text-[22px] font-semibold tracking-[-0.01em] mb-2">Sauvage EDP 100 ml</h3>
        <p className="text-[13px] text-muted-foreground leading-relaxed">
          Five retailers, one canonical record. Same SKU, every store, every change tracked.
        </p>
      </div>

      {/* Price comparison */}
      <div className="bg-background flex flex-col">
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Price comparison · 5 stores
          </span>
          <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
            spread <span className="text-foreground">24%</span>
          </span>
        </div>
        <div className="divide-y divide-border flex-1">
          {SAMPLE_OFFERS.map((o, i) => (
            <div
              key={o.store}
              className={`flex items-center gap-3 px-5 py-3.5 transition-colors ${i === 0 ? "bg-success/[0.06]" : ""}`}
              style={{
                opacity: revealed ? 1 : 0,
                transform: revealed ? "translateX(0)" : "translateX(10px)",
                transition: `opacity 0.5s ease-out ${i * 90}ms, transform 0.5s ease-out ${i * 90}ms`,
              }}
            >
              <span className="w-8 h-6 rounded-sm bg-surface-2 border border-border font-mono text-[10px] font-medium text-muted-foreground flex items-center justify-center shrink-0">
                {o.tag}
              </span>
              <span className="text-[12.5px] text-foreground flex-1 truncate">{o.store}</span>
              <div className="hidden sm:block w-16 h-1 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-muted-foreground/40 rounded-full"
                  style={{
                    width: revealed ? `${o.fillPct}%` : "0%",
                    transition: `width 0.9s ease-out ${i * 90 + 200}ms`,
                  }}
                />
              </div>
              <span
                className={`font-mono tabular-nums font-semibold text-[13px] shrink-0 w-[68px] text-right ${i === 0 ? "text-success" : "text-foreground"}`}
              >
                {o.price.toFixed(2)} €
              </span>
              {i === 0 && (
                <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-success font-semibold shrink-0">
                  Best
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────
 *  Workflow Timeline — Section C
 * ───────────────────────────────────────────────────────────────── */

const WorkflowTimeline = () => {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref}>
      {/* Desktop horizontal */}
      <div className="hidden md:block relative pt-2">
        <div
          aria-hidden
          className="absolute top-7 left-[12.5%] right-[12.5%] h-px bg-border origin-left"
          style={{
            transform: revealed ? "scaleX(1)" : "scaleX(0)",
            transition: "transform 1.4s cubic-bezier(0.22, 1, 0.36, 1) 200ms",
          }}
        />
        <div className="grid grid-cols-3 relative">
          {STEPS.map((s, i) => (
            <div
              key={s.n}
              className="px-6 group"
              style={{
                opacity: revealed ? 1 : 0,
                transform: revealed ? "translateY(0)" : "translateY(16px)",
                transition: `opacity 0.6s ease-out ${i * 180 + 400}ms, transform 0.6s ease-out ${i * 180 + 400}ms`,
              }}
            >
              <div className="w-14 h-14 rounded-full bg-background border-2 border-primary/40 flex items-center justify-center mb-6 group-hover:border-primary group-hover:shadow-[0_0_24px_hsl(var(--primary)/.3)] transition-all duration-300">
                <span className="font-mono text-[14px] text-primary font-semibold tracking-wider">{s.n}</span>
              </div>
              <h3 className="font-display text-[19px] font-semibold text-foreground mb-3 tracking-[-0.01em] group-hover:text-primary transition-colors">
                {s.title}
              </h3>
              <p className="text-[14px] text-muted-foreground leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Mobile vertical */}
      <div className="md:hidden relative">
        <div
          aria-hidden
          className="absolute left-[27px] top-7 bottom-7 w-px bg-border origin-top"
          style={{
            transform: revealed ? "scaleY(1)" : "scaleY(0)",
            transition: "transform 1.6s ease-out 200ms",
          }}
        />
        <div className="space-y-10">
          {STEPS.map((s, i) => (
            <div
              key={s.n}
              className="flex gap-5 relative"
              style={{
                opacity: revealed ? 1 : 0,
                transform: revealed ? "translateX(0)" : "translateX(-12px)",
                transition: `opacity 0.6s ease-out ${i * 180 + 400}ms, transform 0.6s ease-out ${i * 180 + 400}ms`,
              }}
            >
              <div className="w-14 h-14 rounded-full bg-background border-2 border-primary/40 flex items-center justify-center shrink-0 relative z-10">
                <span className="font-mono text-[14px] text-primary font-semibold tracking-wider">{s.n}</span>
              </div>
              <div className="pt-2.5">
                <h3 className="font-display text-[19px] font-semibold text-foreground mb-2 tracking-[-0.01em]">
                  {s.title}
                </h3>
                <p className="text-[14px] text-muted-foreground leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────
 *  Pillars Bento — Section E
 * ───────────────────────────────────────────────────────────────── */

const PillarsBento = () => {
  const Large = PILLARS[0];
  const small = PILLARS.slice(1);
  const accents = [<CornerSparkline key="0" />, <CornerTypingDots key="1" />, <CornerPing key="2" />];

  return (
    <div className="grid md:grid-cols-3 md:grid-rows-[auto_auto] gap-px bg-border rounded-card overflow-hidden border border-border">
      {/* Large — col 1-2, row 1-2 */}
      <div className="md:col-span-2 md:row-span-2 bg-background p-8 md:p-12 relative overflow-hidden group">
        <div className="relative z-10 max-w-md">
          <div className="inline-flex items-center gap-2 mb-7">
            <Large.icon className="w-5 h-5 text-primary" strokeWidth={1.75} />
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Foundation</span>
          </div>
          <h3 className="font-display text-[26px] md:text-[32px] font-semibold text-foreground mb-4 tracking-[-0.015em] leading-[1.15]">
            {Large.title}
          </h3>
          <p className="text-[15px] md:text-[16px] text-muted-foreground leading-[1.65]">{Large.desc}</p>
          <div className="mt-7 inline-flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
            <span className="relative flex w-1.5 h-1.5">
              <span className="absolute inline-flex w-full h-full rounded-full bg-primary opacity-75 animate-ping" />
              <span className="relative inline-flex w-1.5 h-1.5 rounded-full bg-primary" />
            </span>
            Last scan · 14 minutes ago
          </div>
        </div>
        <div aria-hidden className="absolute -right-10 -bottom-10 pointer-events-none">
          <DotMatrix />
        </div>
      </div>

      {/* 3 small */}
      {small.map((p, i) => (
        <div key={p.title} className="bg-background p-7 relative">
          <p.icon className="w-5 h-5 text-primary mb-4" strokeWidth={1.75} />
          <h3 className="font-display text-[16px] font-semibold text-foreground mb-2.5 tracking-[-0.01em]">
            {p.title}
          </h3>
          <p className="text-[13px] text-muted-foreground leading-relaxed">{p.desc}</p>
          <div className="absolute top-5 right-5 opacity-50">{accents[i]}</div>
        </div>
      ))}
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────
 *  Output demos — Section F
 * ───────────────────────────────────────────────────────────────── */

const OUTPUTS = [
  {
    title: "CSV · Excel · JSON",
    desc: "Raw exports of any time window.",
    icon: FileText,
    demo: (
      <pre className="font-mono text-[10px] text-muted-foreground bg-surface-2/60 border border-border rounded p-3 leading-[1.55] overflow-hidden">
{`{
  "sku":   "MP-1023",
  "store": "notino.lv",
  "price": 62.90,
  "delta": -7.4
}`}
      </pre>
    ),
  },
  {
    title: "PDF reports",
    desc: "Formatted summaries for stakeholders.",
    icon: FileText,
    demo: <PdfMockup />,
  },
  {
    title: "Telegram · Email",
    desc: "Threshold-based routing for alerts.",
    icon: Radio,
    demo: (
      <div className="space-y-1.5">
        <div className="bg-surface-2/60 border border-border rounded-md p-2.5 text-[11px] flex items-start gap-2">
          <ArrowDown className="w-3 h-3 text-success mt-0.5 shrink-0" strokeWidth={2.5} />
          <span className="text-foreground leading-relaxed">
            <span className="font-semibold">Dior Sauvage EDP</span> dropped <span className="text-success font-mono">−7.4%</span> on Notino
          </span>
        </div>
        <div className="bg-surface-2/40 border border-border rounded-md p-2 text-[10px] text-muted-foreground italic">
          Delivered 14:02 · via Telegram
        </div>
      </div>
    ),
  },
  {
    title: "Your data stays yours",
    desc: "Independent. No resale, no aggregation.",
    icon: Lock,
    demo: (
      <ul className="space-y-1.5 text-[11.5px]">
        {["No resale", "No aggregation", "No third-party brokers"].map((t) => (
          <li key={t} className="flex items-center gap-2 text-foreground">
            <span className="w-3.5 h-3.5 rounded-full border border-success/50 bg-success/10 flex items-center justify-center shrink-0">
              <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                <path d="M1.5 4 L3 5.5 L6.5 2" stroke="hsl(var(--success))" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span>{t}</span>
          </li>
        ))}
      </ul>
    ),
  },
];

/* ─────────────────────────────────────────────────────────────────
 *  Page
 * ───────────────────────────────────────────────────────────────── */

const Index = () => {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      {/* ═════════════════════ HEADER ═════════════════════ */}
      <header className="sticky top-0 z-50 h-16 border-b border-border bg-background/85 backdrop-blur-lg">
        <div className="max-w-7xl mx-auto h-full px-5 md:px-8 flex items-center justify-between">
          <div className="flex items-center gap-10">
            <div className="flex items-center gap-2.5">
              <img src={logoImg} alt="MarketPulse" className="h-8 w-auto shrink-0" />
              <span className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">MarketPulse</span>
            </div>
            <nav className="hidden md:flex items-center gap-7">
              {["Platform", "Coverage", "Pricing", "Docs"].map((l) => (
                <a
                  key={l}
                  href="#"
                  className="text-[13.5px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  {l}
                </a>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate("/signin")}
              className="text-[13.5px] text-muted-foreground hover:text-foreground px-3 py-2 transition-colors"
            >
              Sign in
            </button>
            <button
              onClick={() => navigate("/register")}
              className="text-[13.5px] font-medium bg-foreground text-background rounded-md px-4 py-2 hover:bg-foreground/90 transition-colors"
            >
              Get started →
            </button>
          </div>
        </div>
      </header>

      {/* ═════════════════════ HERO ═════════════════════ */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="absolute left-1/2 -translate-x-1/2 bottom-[-200px] w-[900px] h-[500px] rounded-full pointer-events-none"
          style={{ background: "hsl(var(--primary))", filter: "blur(140px)", opacity: 0.14 }}
        />

        <div className="relative max-w-5xl mx-auto px-5 md:px-8 pt-28 md:pt-40 pb-28 md:pb-40">
          <Reveal>
            <span className="inline-flex items-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-10">
              Perfume price intelligence · Latvian market
            </span>
          </Reveal>

          <Reveal delayMs={80}>
            <h1 className="font-['Inter'] font-semibold text-foreground text-[32px] sm:text-[40px] md:text-[48px] leading-[1.1] tracking-[-0.02em]">
              The{" "}
              <span
                className="animate-shimmer bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(90deg, hsl(var(--foreground)) 0%, hsl(var(--primary)) 45%, hsl(var(--foreground)) 75%)",
                }}
              >
                pricing edge
              </span>
              ,
              <br />
              without the spreadsheet.
            </h1>
          </Reveal>

          <Reveal delayMs={180}>
            <p className="max-w-2xl mt-8 text-[17px] md:text-[19px] text-muted-foreground leading-[1.55]">
              MarketPulse captures every price change across Douglas, Notino, Makeup.lv, 1a.lv and 220.lv — twice a day,
              every day. No feeds, no estimates. What the customer sees is what we record.
            </p>
          </Reveal>

          <Reveal delayMs={260}>
            <div className="flex flex-wrap items-center gap-3 mt-10">
              <button
                onClick={() => navigate("/register")}
                className="text-[14px] font-medium bg-foreground text-background rounded-md px-5 py-3 hover:bg-foreground/90 hover:shadow-[0_8px_24px_-8px_hsl(var(--primary)/.4)] transition-all inline-flex items-center gap-1.5"
              >
                Start monitoring free
                <ArrowUpRight className="w-4 h-4" />
              </button>
              <a
                href="#platform"
                className="text-[14px] font-medium text-foreground rounded-md px-5 py-3 hover:bg-surface-2 transition-colors border border-border"
              >
                Platform tour
              </a>
            </div>
          </Reveal>

          <Reveal delayMs={340}>
            <p className="mt-8 text-[12px] text-muted-foreground">
              <span className="font-mono">/</span> Free for 5 monitored SKUs · No card required · 12-month history
            </p>
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════ TRUST STRIP — MARQUEE ═════════════════════ */}
      <section className="border-y border-border bg-surface/30 py-7 group/marquee overflow-hidden">
        <p className="text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-5">
          Covering pricing from
        </p>
        <div
          className="flex gap-14 animate-marquee-scroll group-hover/marquee:[animation-play-state:paused]"
          aria-hidden="false"
        >
          {[...STORES, ...STORES, ...STORES].map((s, i) => (
            <div key={i} className="flex items-baseline gap-3 shrink-0">
              <span className="text-[18px] md:text-xl font-semibold tracking-[-0.02em] text-muted-foreground hover:text-foreground transition-colors">
                {s.name}
                <span className="text-primary/50 font-mono font-normal text-[14px] ml-1">.lv</span>
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/60">
                · monitored 12mo
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ═════════════════════ SECTION A — PROBLEM + CHART ═════════════════════ */}
      <section id="platform" className="py-24 md:py-36 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto grid md:grid-cols-[0.9fr_1.1fr] gap-12 md:gap-20 items-center">
          <Reveal>
            <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">01 · The problem</p>
            <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
              Prices move faster than you check them.
            </h2>
            <p className="mt-6 text-[16px] text-muted-foreground leading-[1.65] max-w-md">
              Douglas cut Dior Sauvage 7.4% on a Tuesday afternoon. If you were checking on Wednesday evening, you paid
              the old price. MarketPulse closes that window.
            </p>
            <div className="mt-8 space-y-3">
              {[
                "Every retailer, every SKU, twice daily",
                "Drift-free history across twelve months",
                "Cross-store comparison on any given day",
              ].map((t) => (
                <div key={t} className="flex items-start gap-3 text-[14px] text-foreground">
                  <span className="w-1 h-1 rounded-full bg-primary mt-2.5 shrink-0" />
                  {t}
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delayMs={120}>
            <PriceTimelineChart />
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════ SECTION B — STATS BAND ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <Reveal>
            <div className="max-w-3xl mb-14">
              <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">02 · The data</p>
              <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
                The numbers that back the decisions.
              </h2>
            </div>
          </Reveal>
          <StatsBand />
        </div>
      </section>

      {/* ═════════════════════ SECTION 02.5 — SAMPLE SKU SHOWCASE ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <Reveal>
            <div className="max-w-3xl mb-14">
              <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">02.5 · Example</p>
              <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
                One SKU, five truths.
              </h2>
              <p className="mt-6 text-[16px] text-muted-foreground leading-[1.65] max-w-2xl">
                Each product carries every retailer's offer side by side. The cheapest is highlighted. The spread is
                quantified. The history is one click away.
              </p>
            </div>
          </Reveal>
          <Reveal delayMs={100}>
            <SampleSku />
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════ SECTION C — WORKFLOW TIMELINE ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <Reveal>
            <div className="max-w-3xl mb-14">
              <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">03 · Workflow</p>
              <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
                Three steps to a monitoring set.
              </h2>
            </div>
          </Reveal>
          <WorkflowTimeline />
        </div>
      </section>

      {/* ═════════════════════ SECTION D — AI ASSISTANT ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto grid md:grid-cols-[1.1fr_0.9fr] gap-12 md:gap-20 items-center">
          <Reveal>
            <AiTranscript />
          </Reveal>
          <Reveal delayMs={120}>
            <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">04 · Analysis</p>
            <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
              Ask in English. Get numbers.
            </h2>
            <p className="mt-6 text-[16px] text-muted-foreground leading-[1.65] max-w-md">
              The assistant queries your monitored set directly. No hallucinated market averages, no generic advice —
              just numbers pulled from the history table you own.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-px bg-border rounded-md overflow-hidden border border-border max-w-sm">
              {[
                { label: "Query", value: "~0.8s" },
                { label: "Accuracy", value: "Source-linked" },
              ].map((m) => (
                <div key={m.label} className="bg-background px-4 py-4">
                  <p className="font-display font-semibold text-foreground text-[22px] tracking-[-0.02em] tabular-nums">
                    {m.value}
                  </p>
                  <p className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground mt-1.5 font-medium">
                    {m.label}
                  </p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════ SECTION E — PILLARS BENTO ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <Reveal>
            <div className="max-w-3xl mb-14">
              <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">05 · Design</p>
              <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
                Built for analysts, not for hype.
              </h2>
              <p className="mt-6 text-[16px] text-muted-foreground leading-[1.65] max-w-2xl">
                MarketPulse is opinionated about what a pricing tool should do — and what it should quietly refuse to be.
              </p>
            </div>
          </Reveal>
          <Reveal delayMs={100}>
            <PillarsBento />
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════ SECTION F — OUTPUT TYPED DEMOS ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <Reveal>
            <div className="max-w-3xl mb-14">
              <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">06 · Output</p>
              <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
                Your data, wherever you need it.
              </h2>
            </div>
          </Reveal>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-px bg-border rounded-card overflow-hidden border border-border">
            {OUTPUTS.map((o, i) => (
              <Reveal key={o.title} delayMs={i * 90}>
                <div className="bg-background p-6 h-full flex flex-col">
                  <div className="mb-5 flex-1 min-h-[88px]">{o.demo}</div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <o.icon className="w-3.5 h-3.5 text-primary" strokeWidth={1.75} />
                    <h3 className="font-display text-[14.5px] font-semibold text-foreground tracking-[-0.005em]">
                      {o.title}
                    </h3>
                  </div>
                  <p className="text-[12.5px] text-muted-foreground leading-relaxed">{o.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ═════════════════════ CTA ═════════════════════ */}
      <section className="py-28 md:py-40 px-5 md:px-8 relative overflow-hidden">
        <div
          aria-hidden
          className="absolute left-1/2 -translate-x-1/2 top-1/2 -translate-y-1/2 w-[700px] h-[300px] rounded-full pointer-events-none"
          style={{ background: "hsl(var(--primary))", filter: "blur(160px)", opacity: 0.12 }}
        />
        {/* Floating dots */}
        <div aria-hidden className="absolute inset-0 pointer-events-none">
          {[
            { top: "18%", left: "12%", size: 4, delay: 0 },
            { top: "32%", left: "82%", size: 3, delay: 0.8 },
            { top: "55%", left: "18%", size: 2, delay: 1.5 },
            { top: "68%", left: "78%", size: 4, delay: 0.4 },
            { top: "78%", left: "44%", size: 3, delay: 1.1 },
          ].map((d, i) => (
            <span
              key={i}
              className="absolute rounded-full bg-primary/40 animate-drift-slow"
              style={{
                top: d.top,
                left: d.left,
                width: `${d.size}px`,
                height: `${d.size}px`,
                animationDelay: `${d.delay}s`,
              }}
            />
          ))}
        </div>

        <div className="relative max-w-3xl mx-auto text-center">
          <Reveal>
            <h2 className="font-display font-semibold text-foreground text-[34px] md:text-5xl leading-[1.05] tracking-[-0.03em]">
              Start with five products.
              <br />
              Scale when the data proves itself.
            </h2>
            <p className="mt-6 text-[16px] text-muted-foreground max-w-xl mx-auto leading-[1.65]">
              No card required. No contract. The free tier is permanent and sufficient for most enthusiasts.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 mt-9">
              <button
                onClick={() => navigate("/register")}
                className="text-[14px] font-medium bg-foreground text-background rounded-md px-6 py-3.5 hover:bg-foreground/90 hover:shadow-[0_8px_24px_-8px_hsl(var(--primary)/.4)] transition-all inline-flex items-center gap-1.5"
              >
                Create account
                <ArrowUpRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => navigate("/signin")}
                className="text-[14px] font-medium text-foreground rounded-md px-6 py-3.5 hover:bg-surface-2 transition-colors border border-border"
              >
                Sign in
              </button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ═════════════════════ FOOTER ═════════════════════ */}
      <footer className="border-t border-border py-14 px-5 md:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-5 gap-10 md:gap-14 mb-12">
            <div className="md:col-span-2">
              <div className="flex items-center gap-2.5 mb-5">
                <img src={logoImg} alt="MarketPulse" className="h-7 w-auto" />
                <span className="text-[14px] font-semibold tracking-[-0.01em] text-foreground">MarketPulse</span>
              </div>
              <p className="text-[13px] text-muted-foreground leading-relaxed max-w-sm">
                Perfume price intelligence for the Latvian market. Built independently, in Riga.
              </p>
            </div>
            {[
              { title: "Platform", items: ["Features", "Pricing", "Coverage", "Changelog"] },
              { title: "Resources", items: ["Documentation", "API", "Status", "Support"] },
              { title: "Company", items: ["About", "Contact", "Privacy", "Terms"] },
            ].map((col) => (
              <div key={col.title}>
                <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-semibold mb-4">
                  {col.title}
                </p>
                <ul className="space-y-2.5">
                  {col.items.map((it) => (
                    <li key={it}>
                      <a href="#" className="text-[13px] text-muted-foreground hover:text-foreground transition-colors">
                        {it}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="pt-6 border-t border-border flex flex-col md:flex-row items-center justify-between gap-3 text-[12px] text-muted-foreground">
            <span>© 2026 MarketPulse. All prices belong to their respective retailers.</span>
            <span className="font-mono text-[11px]">v1.0 · marketpulse.lv</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
