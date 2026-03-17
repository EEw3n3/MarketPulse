import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, Bot, ChevronRight, Bell, BarChart3, MessageSquare, Droplets } from "lucide-react";
import AuthModal from "@/components/AuthModal";
import OnboardingModal from "@/components/OnboardingModal";
import OnboardingStep2 from "@/components/OnboardingStep2";

/* ── Starfield ────────────────────────────────────────────────── */
const Stars = () => {
  const stars = useMemo(
    () =>
      Array.from({ length: 40 }, (_, i) => ({
        id: i,
        left: Math.random() * 100,
        top: Math.random() * 100,
        size: 1 + Math.random() * 2,
        delay: Math.random() * 6,
        duration: 3 + Math.random() * 4,
      })),
    [],
  );

  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden z-0" aria-hidden>
      {stars.map((s) => (
        <span
          key={s.id}
          className="absolute rounded-full bg-foreground/30 animate-twinkle"
          style={{
            left: `${s.left}%`,
            top: `${s.top}%`,
            width: s.size,
            height: s.size,
            animationDelay: `${s.delay}s`,
            animationDuration: `${s.duration}s`,
          }}
        />
      ))}
    </div>
  );
};

/* ── Mini Price Chart (SVG) ───────────────────────────────────── */
const MiniChart = () => (
  <svg viewBox="0 0 200 80" className="w-full h-full" fill="none">
    <defs>
      <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="hsl(var(--success))" stopOpacity="0.3" />
        <stop offset="100%" stopColor="hsl(var(--success))" stopOpacity="0" />
      </linearGradient>
    </defs>
    <path
      d="M0 60 Q20 55 40 50 T80 35 T120 40 T160 20 T200 25"
      stroke="hsl(var(--success))"
      strokeWidth="2"
      strokeLinecap="round"
    />
    <path
      d="M0 60 Q20 55 40 50 T80 35 T120 40 T160 20 T200 25 V80 H0Z"
      fill="url(#chartGrad)"
    />
  </svg>
);

/* ── Showcase Cards ───────────────────────────────────────────── */
const ShowcaseCards = () => (
  <div className="flex flex-col sm:flex-row items-center justify-center gap-5 mt-14 px-4">
    {/* Product card */}
    <div className="glass-card p-5 w-64 animate-float" style={{ animationDelay: "0s", transform: "rotate(-12deg)" }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
          <Droplets className="w-3.5 h-3.5 text-primary" />
          Dior Sauvage EDP
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-success bg-success/10 px-2 py-0.5 rounded-button">
          <ArrowDown className="w-3 h-3" /> 8.5%
        </span>
      </div>
      <p className="font-display text-3xl font-bold tracking-tightest price-display text-foreground">125.00 €</p>
      <p className="text-xs text-muted-foreground mt-2">Douglas · 3 min ago</p>
    </div>

    {/* Mini chart card */}
    <div className="glass-card p-5 w-64 animate-float" style={{ animationDelay: "1s", transform: "rotate(4deg)" }}>
      <p className="text-xs font-medium text-muted-foreground mb-2">30-Day Price Trend</p>
      <div className="h-20">
        <MiniChart />
      </div>
      <div className="flex justify-between mt-2 text-[10px] text-muted-foreground">
        <span>Feb 14</span>
        <span>Mar 16</span>
      </div>
    </div>

    {/* AI chat preview */}
    <div className="glass-card p-5 w-64 animate-float" style={{ animationDelay: "2s", transform: "rotate(20deg)" }}>
      <div className="flex items-center gap-2 mb-3">
        <Bot className="w-4 h-4 text-primary" />
        <span className="text-xs font-medium text-muted-foreground">AI Assistant</span>
      </div>
      <div className="bg-surface-2 rounded-lg p-2.5 mb-2">
        <p className="text-xs text-foreground">"When was the last price drop for Bleu de Chanel?"</p>
      </div>
      <div className="bg-primary/10 rounded-lg p-2.5">
        <p className="text-xs text-foreground">
          "It dropped 12% on Mar 2 at Notino — from 98€ to 86€."
        </p>
      </div>
    </div>
  </div>
);

/* ── Features Row ─────────────────────────────────────────────── */
const features = [
  {
    icon: Bell,
    title: "Instant Alerts",
    desc: "Telegram, SMS & Email notifications the moment prices change.",
  },
  {
    icon: BarChart3,
    title: "Price History",
    desc: "Full year of historical charts across all major retailers.",
  },
  {
    icon: MessageSquare,
    title: "AI Assistant",
    desc: "Ask anything about market data — powered by intelligent analysis.",
  },
];

/* ── Page ─────────────────────────────────────────────────────── */
const Index = () => {
  const navigate = useNavigate();
  const [authOpen, setAuthOpen] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState<null | 1 | 2>(null);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} onRegister={() => { setAuthOpen(false); setOnboardingStep(1); }} onSignIn={() => navigate("/dashboard")} />
      <OnboardingModal open={onboardingStep === 1} onClose={() => setOnboardingStep(null)} onNext={() => setOnboardingStep(2)} />
      <OnboardingStep2 open={onboardingStep === 2} onClose={() => { setOnboardingStep(null); navigate("/dashboard", { state: { showTutorial: true } }); }} onBack={() => setOnboardingStep(1)} />
      {/* Animated gradient background */}
      <div
        className="fixed inset-0 z-0 animate-gradient-shift"
        style={{
          background: "linear-gradient(135deg, #0A0A0F 0%, #1a0533 50%, #0A0A0F 100%)",
          backgroundSize: "200% 200%",
        }}
      />
      <Stars />

      {/* Sticky Header */}
      <header className="sticky top-0 z-50 h-16 flex items-center justify-between px-5 md:px-10 border-b border-border/50 bg-background/60 backdrop-blur-xl">
        <div className="flex items-center gap-2.5">
          {/* Hexagon logo */}
          <svg width="28" height="32" viewBox="0 0 28 32" fill="none" className="shrink-0">
            <path
              d="M14 0L27.856 8V24L14 32L0.144 24V8L14 0Z"
              fill="hsl(var(--primary))"
            />
            <text
              x="14"
              y="20"
              textAnchor="middle"
              fill="white"
              fontSize="14"
              fontWeight="700"
              fontFamily="Outfit, sans-serif"
            >
              M
            </text>
          </svg>
          <span className="font-display text-xl font-bold text-foreground">
            Market<span className="text-primary">Pulse</span>
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setAuthOpen(true)}
            className="hidden sm:inline-flex items-center justify-center text-sm font-medium border border-primary text-primary rounded-button px-4 py-2 transition-all ease-brand hover:bg-primary/10"
          >
            Sign In
          </button>
          <button
            onClick={() => setAuthOpen(true)}
            className="btn-primary text-sm px-5 py-2"
          >
            Get Started
          </button>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 flex flex-col items-center justify-center text-center px-5" style={{ minHeight: "calc(80vh - 64px)" }}>
        {/* Badge */}
        <div
          className="inline-flex items-center gap-2 border border-secondary/40 rounded-full px-4 py-1.5 mb-8 opacity-0 animate-fade-in"
          style={{ animationDelay: "0.1s" }}
        >
          <span className="text-secondary text-sm">✦</span>
          <span className="text-xs text-muted-foreground font-medium">Real-time price monitoring</span>
        </div>

        {/* H1 */}
        <h1
          className="font-display text-5xl md:text-6xl font-extrabold tracking-tightest leading-[1.1] opacity-0 animate-fade-in"
          style={{ animationDelay: "0.25s" }}
        >
          Track Prices.
          <br />
          Shop <span className="gradient-text">Smarter.</span>
        </h1>

        {/* Subheadline */}
        <p
          className="mt-5 text-[15px] text-muted-foreground max-w-[520px] leading-relaxed opacity-0 animate-fade-in"
          style={{ animationDelay: "0.4s" }}
        >
          MarketPulse monitors perfume prices across Douglas, Notino, 220.lv, Makeup.lv, and 1a.lv. Be the first to know about drops and changes.
        </p>

        {/* CTA */}
        <div className="mt-8 opacity-0 animate-fade-in" style={{ animationDelay: "0.55s" }}>
          <button onClick={() => setAuthOpen(true)} className="btn-primary text-base px-8 py-3.5 hover:scale-[1.04] transition-transform ease-brand">
            Start for Free <ChevronRight className="w-4 h-4 ml-1 inline" />
          </button>
          <p className="text-[11px] text-muted-foreground mt-3">Takes 30 seconds. No credit card required.</p>
        </div>

      </section>

      {/* Showcase — separated from hero */}
      <section className="relative z-10 pb-12 opacity-0 animate-fade-in" style={{ animationDelay: "0.7s" }}>
        <ShowcaseCards />
      </section>

      {/* Features */}
      <section className="relative z-10 py-24 px-5">
        <div className="max-w-4xl mx-auto grid sm:grid-cols-3 gap-6">
          {features.map((f, i) => (
            <div
              key={f.title}
              className="glass-card p-6 text-center opacity-0 animate-fade-in"
              style={{ animationDelay: `${0.9 + i * 0.15}s` }}
            >
              <div className="inline-flex items-center justify-center w-11 h-11 rounded-card bg-primary/10 mb-4">
                <f.icon className="w-5 h-5 text-primary" />
              </div>
              <h3 className="font-display text-lg font-bold text-foreground mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border/50 py-6 px-5">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>© 2026 MarketPulse</span>
          <div className="flex gap-5">
            <a href="#" className="hover:text-foreground transition-colors ease-brand">Privacy</a>
            <a href="#" className="hover:text-foreground transition-colors ease-brand">Terms</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
