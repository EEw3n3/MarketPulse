import { useNavigate } from "react-router-dom";
import logoImg from "@/assets/logo.png";
import {
  ArrowDown,
  ArrowUpRight,
  Bell,
  Bot,
  Database,
  Download,
  FileText,
  LineChart,
  Lock,
  Radio,
  Shield,
} from "lucide-react";

/* ─────────────────────────────────────────────────────────────────
 *  MarketPulse — Landing page (editorial long-form, B2B analytics)
 *  Pattern references: Snowflake, AWS Redshift, Kaggle.
 *  No fake dashboard cards in hero. Typography-driven. Wide whitespace.
 * ───────────────────────────────────────────────────────────────── */

const STORES = [
  { name: "Douglas", domain: "douglas.lv" },
  { name: "Notino", domain: "notino.lv" },
  { name: "Makeup", domain: "makeup.lv" },
  { name: "1A.lv", domain: "1a.lv" },
  { name: "220.lv", domain: "220.lv" },
];

const STATS = [
  { value: "5", label: "Retailers covered" },
  { value: "1,200+", label: "SKUs monitored" },
  { value: "4,800+", label: "Price checks / day" },
  { value: "12mo", label: "History retained" },
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

/* ── Lightweight SVG price chart (real axis, no decorative gradients) ── */
const PriceTimelineChart = () => {
  const lines = [
    { store: "Douglas", color: "hsl(217, 91%, 60%)", d: "M0 60 L50 55 L100 58 L150 50 L200 44 L250 40 L300 36 L350 35" },
    { store: "Notino", color: "hsl(var(--primary))", d: "M0 70 L50 65 L100 60 L150 58 L200 50 L250 46 L300 42 L350 38" },
    { store: "Makeup", color: "hsl(330, 70%, 55%)", d: "M0 80 L50 78 L100 72 L150 70 L200 66 L250 62 L300 58 L350 56" },
    { store: "1a.lv", color: "hsl(25, 85%, 55%)", d: "M0 90 L50 92 L100 88 L150 90 L200 86 L250 85 L300 82 L350 80" },
    { store: "220.lv", color: "hsl(45, 80%, 55%)", d: "M0 100 L50 102 L100 98 L150 100 L200 96 L250 94 L300 92 L350 90" },
  ];

  return (
    <div className="bg-surface border border-border rounded-card overflow-hidden">
      {/* Header row */}
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
          {/* Gridlines */}
          {[20, 50, 80, 110].map((y) => (
            <line key={y} x1="0" y1={y} x2="380" y2={y} stroke="hsl(var(--border))" strokeWidth="1" strokeDasharray="2 3" />
          ))}
          {/* Y-axis price labels */}
          <text x="360" y="24" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">
            145 €
          </text>
          <text x="360" y="54" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">
            135 €
          </text>
          <text x="360" y="84" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">
            125 €
          </text>
          <text x="360" y="114" fontSize="9" fill="hsl(var(--muted-foreground))" textAnchor="end" fontFamily="Geist Mono">
            115 €
          </text>

          {lines.map((l) => (
            <path key={l.store} d={l.d} stroke={l.color} strokeWidth="1.8" fill="none" strokeLinecap="round" />
          ))}

          {/* Highlight point — Douglas drop */}
          <circle cx="300" cy="36" r="4" fill="hsl(var(--success))" />
          <circle cx="300" cy="36" r="8" fill="hsl(var(--success))" fillOpacity="0.2" />
        </svg>

        {/* X-axis */}
        <div className="flex justify-between mt-2 text-[10px] text-muted-foreground tabular-nums font-mono">
          <span>Dec</span>
          <span>Jan</span>
          <span>Feb</span>
          <span>Mar</span>
        </div>

        {/* Legend */}
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
      <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-surface-2/40 text-[11px]">
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

/* ── AI conversation mock (Section D) ─────────────────────────── */
const AiTranscript = () => (
  <div className="bg-surface border border-border rounded-card overflow-hidden">
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
        <p className="text-sm text-foreground leading-relaxed">
          Hugo Boss Bottled EDP 100 ml at{" "}
          <span className="font-mono font-semibold text-foreground">62.90 €</span> on Notino — its lowest in 3 months.
          Douglas is 68.50 € (+8.9%) and 1a.lv is out of stock.
        </p>
        <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="w-1 h-1 rounded-full bg-primary" />
          Based on 247 price points · queried in 0.8s
        </div>
      </div>
    </div>
  </div>
);

/* ── Page ───────────────────────────────────────────────────────── */
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
        {/* Ambient glow at bottom center */}
        <div
          aria-hidden
          className="absolute left-1/2 -translate-x-1/2 bottom-[-200px] w-[900px] h-[500px] rounded-full pointer-events-none"
          style={{ background: "hsl(var(--primary))", filter: "blur(140px)", opacity: 0.14 }}
        />

        <div className="relative max-w-5xl mx-auto px-5 md:px-8 pt-28 md:pt-40 pb-28 md:pb-40">
          <span className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-10">
            <span className="relative flex w-1.5 h-1.5">
              <span className="absolute inline-flex w-full h-full rounded-full bg-primary opacity-75 animate-ping" />
              <span className="relative inline-flex w-1.5 h-1.5 rounded-full bg-primary" />
            </span>
            Perfume price intelligence · Latvian market
          </span>

          <h1 className="font-['Inter'] font-semibold text-foreground text-[32px] sm:text-[40px] md:text-[48px] leading-[1.1] tracking-[-0.02em]">
            The pricing edge,
            <br />
            without the spreadsheet.
          </h1>

          <p className="max-w-2xl mt-8 text-[17px] md:text-[19px] text-muted-foreground leading-[1.55]">
            MarketPulse captures every price change across Douglas, Notino, Makeup.lv, 1a.lv and 220.lv — twice a day,
            every day. No feeds, no estimates. What the customer sees is what we record.
          </p>

          <div className="flex flex-wrap items-center gap-3 mt-10">
            <button
              onClick={() => navigate("/register")}
              className="text-[14px] font-medium bg-foreground text-background rounded-md px-5 py-3 hover:bg-foreground/90 transition-colors inline-flex items-center gap-1.5"
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

          <p className="mt-8 text-[12px] text-muted-foreground">
            <span className="font-mono">/</span> Free for 5 monitored SKUs · No card required · 12-month history
          </p>
        </div>
      </section>

      {/* ═════════════════════ TRUST STRIP (retailer coverage) ═════════════════════ */}
      <section className="border-y border-border bg-surface/30">
        <div className="max-w-7xl mx-auto px-5 md:px-8 py-10">
          <p className="text-center text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-7">
            Covering pricing from
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4">
            {STORES.map((s) => (
              <span
                key={s.name}
                className="text-[18px] md:text-xl font-semibold tracking-[-0.02em] text-muted-foreground hover:text-foreground transition-colors"
              >
                {s.name}
                <span className="text-primary/50 font-mono font-normal text-[14px] ml-1">.lv</span>
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ═════════════════════ SECTION A — THE PROBLEM + CHART ═════════════════════ */}
      <section id="platform" className="py-24 md:py-36 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto grid md:grid-cols-[0.9fr_1.1fr] gap-12 md:gap-20 items-center">
          <div>
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
          </div>
          <div>
            <PriceTimelineChart />
          </div>
        </div>
      </section>

      {/* ═════════════════════ SECTION B — STATS BAND ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-3xl mb-14">
            <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">02 · The data</p>
            <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
              The numbers that back the decisions.
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-card overflow-hidden border border-border">
            {STATS.map((s) => (
              <div key={s.label} className="bg-background px-7 py-10 md:py-14">
                <p className="font-display font-semibold text-foreground text-[44px] md:text-[64px] leading-none tracking-[-0.04em] tabular-nums">
                  {s.value}
                </p>
                <p className="text-[12px] uppercase tracking-[0.14em] text-muted-foreground mt-4 font-medium">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═════════════════════ SECTION C — HOW IT WORKS ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-3xl mb-14">
            <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">03 · Workflow</p>
            <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
              Three steps to a monitoring set.
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-px bg-border rounded-card overflow-hidden border border-border">
            {STEPS.map((s) => (
              <div key={s.n} className="bg-background p-8 md:p-10">
                <p className="font-mono text-[13px] text-primary mb-5 tracking-wider">{s.n}</p>
                <h3 className="font-display text-[19px] font-semibold text-foreground mb-3 tracking-[-0.01em]">
                  {s.title}
                </h3>
                <p className="text-[14px] text-muted-foreground leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═════════════════════ SECTION D — AI ASSISTANT ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto grid md:grid-cols-[1.1fr_0.9fr] gap-12 md:gap-20 items-center">
          <div>
            <AiTranscript />
          </div>
          <div>
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
          </div>
        </div>
      </section>

      {/* ═════════════════════ SECTION E — PILLARS ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-3xl mb-14">
            <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">05 · Design</p>
            <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
              Built for analysts, not for hype.
            </h2>
            <p className="mt-6 text-[16px] text-muted-foreground leading-[1.65] max-w-2xl">
              MarketPulse is opinionated about what a pricing tool should do — and what it should quietly refuse to be.
            </p>
          </div>
          <div className="grid md:grid-cols-2 gap-px bg-border rounded-card overflow-hidden border border-border">
            {PILLARS.map((p) => (
              <div key={p.title} className="bg-background p-8">
                <p.icon className="w-5 h-5 text-primary mb-5" strokeWidth={1.75} />
                <h3 className="font-display text-[18px] font-semibold text-foreground mb-2.5 tracking-[-0.01em]">
                  {p.title}
                </h3>
                <p className="text-[14px] text-muted-foreground leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═════════════════════ SECTION F — EXPORT / GUARANTEES ═════════════════════ */}
      <section className="py-24 md:py-32 px-5 md:px-8 border-b border-border">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-3xl mb-14">
            <p className="text-[11px] uppercase tracking-[0.18em] text-primary font-medium mb-5">06 · Output</p>
            <h2 className="font-display font-semibold text-foreground text-[32px] md:text-5xl leading-[1.05] tracking-[-0.025em]">
              Your data, wherever you need it.
            </h2>
          </div>
          <div className="grid md:grid-cols-4 gap-px bg-border rounded-card overflow-hidden border border-border">
            {[
              { icon: FileText, title: "CSV · Excel · JSON", desc: "Raw exports of any time window." },
              { icon: Download, title: "PDF reports", desc: "Formatted summaries for non-technical stakeholders." },
              { icon: Radio, title: "Telegram · Email", desc: "Threshold-based routing for alerts." },
              { icon: Lock, title: "Your data stays yours", desc: "No resale, no aggregation, no third-party brokers." },
            ].map((o) => (
              <div key={o.title} className="bg-background p-8">
                <o.icon className="w-5 h-5 text-primary mb-5" strokeWidth={1.75} />
                <h3 className="font-display text-[15px] font-semibold text-foreground mb-2 tracking-[-0.005em]">
                  {o.title}
                </h3>
                <p className="text-[13px] text-muted-foreground leading-relaxed">{o.desc}</p>
              </div>
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
        <div className="relative max-w-3xl mx-auto text-center">
          <Shield className="w-6 h-6 text-primary mx-auto mb-6" strokeWidth={1.5} />
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
              className="text-[14px] font-medium bg-foreground text-background rounded-md px-6 py-3.5 hover:bg-foreground/90 transition-colors inline-flex items-center gap-1.5"
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
