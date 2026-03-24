import { useState, useEffect, useRef } from "react";
import logoImg from "@/assets/logo.png";
import { useNavigate } from "react-router-dom";
import {
  ChevronRight,
  Bell,
  BarChart3,
  MessageSquare,
  ArrowDown,
  ArrowUp,
  Download,
  Share2,
  TrendingDown,
  Store,
  Bot,
  Shield,
  Zap,
  Eye,
  Check,
  FileSpreadsheet,
  FileText,
  FileJson,
  File,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import AuthModal from "@/components/AuthModal";
import OnboardingModal from "@/components/OnboardingModal";
import OnboardingStep2 from "@/components/OnboardingStep2";

/* ── Scroll-triggered fade-in ─────────────────────────────────── */
const useFadeIn = () => {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold: 0.15 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return { ref, className: visible ? "animate-fade-in" : "opacity-0" };
};

const Section = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
  const fade = useFadeIn();
  return (
    <section ref={fade.ref} className={`${fade.className} ${className}`}>
      {children}
    </section>
  );
};

/* ── Animated counter hook (count up when visible) ───────────── */
const useCountUp = (target: number, duration = 1200) => {
  const ref = useRef<HTMLSpanElement>(null);
  const [count, setCount] = useState(0);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setStarted(true); obs.disconnect(); } },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
    let start = 0;
    const step = Math.ceil(target / (duration / 16));
    const timer = setInterval(() => {
      start += step;
      if (start >= target) { setCount(target); clearInterval(timer); }
      else setCount(start);
    }, 16);
    return () => clearInterval(timer);
  }, [started, target, duration]);

  return { ref, count };
};

/* ── Stats counter item ───────────────────────────────────────── */
const StatItem = ({ value, suffix, label }: { value: number; suffix: string; label: string }) => {
  const { ref, count } = useCountUp(value);
  return (
    <div className="text-center px-8 py-6">
      <p className="font-display text-3xl md:text-4xl font-extrabold stat-number">
        <span ref={ref}>{count}</span>
        <span>{suffix}</span>
      </p>
      <p className="text-xs text-muted-foreground mt-1.5 font-medium tracking-wide uppercase">{label}</p>
    </div>
  );
};

/* ── Mini UI Mockups ──────────────────────────────────────────── */
const PriceDropCard = () => (
  <div className="glass-card p-4 space-y-3">
    <div className="flex items-center justify-between">
      <span className="text-xs font-medium text-muted-foreground">Dior Sauvage EDP</span>
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-success bg-success/10 px-2 py-0.5 rounded-full">
        <ArrowDown className="w-3 h-3" /> 8.5%
      </span>
    </div>
    <p className="font-display text-2xl font-bold text-foreground price-display">125.00 €</p>
    <div className="flex items-center gap-2">
      <div className="h-1 flex-1 rounded-full bg-success/20"><div className="h-full w-3/4 rounded-full bg-success" /></div>
      <span className="text-[10px] text-muted-foreground">Best in 30d</span>
    </div>
  </div>
);

const ComparisonTable = () => (
  <div className="glass-card p-4 space-y-2">
    <p className="text-xs font-semibold text-foreground mb-2">Store Comparison</p>
    {[
      { store: "Douglas.lv", price: "125.00 €", best: true },
      { store: "Notino.lv", price: "129.99 €", best: false },
      { store: "1a.lv", price: "134.95 €", best: false },
    ].map((r) => (
      <div key={r.store} className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs ${r.best ? "bg-success/10 border border-success/20" : "bg-surface-2"}`}>
        <span className={r.best ? "text-success font-semibold" : "text-muted-foreground"}>{r.store}</span>
        <span className={r.best ? "text-success font-bold" : "text-foreground"}>{r.price}</span>
      </div>
    ))}
  </div>
);

const AiChatPreview = () => (
  <div className="glass-card p-4 space-y-3">
    <div className="flex items-center gap-2 mb-1">
      <Bot className="w-4 h-4 text-primary" />
      <span className="text-xs font-medium text-muted-foreground">AI Assistant</span>
    </div>
    <div className="bg-surface-2 rounded-lg p-2.5">
      <p className="text-[11px] text-foreground">"What's the cheapest Hugo Boss right now?"</p>
    </div>
    <div className="bg-primary/10 rounded-lg p-2.5">
      <p className="text-[11px] text-foreground">"Hugo Boss Bottled EDP is 62.90 € at Notino — lowest in 3 months."</p>
    </div>
  </div>
);

/* ExportPreview — Lucide SVG icons replacing emoji */
const ExportPreview = () => (
  <div className="glass-card p-4 space-y-3">
    <p className="text-xs font-semibold text-foreground">Export Formats</p>
    <div className="grid grid-cols-2 gap-2">
      {[
        { icon: FileSpreadsheet, label: "CSV" },
        { icon: File, label: "Excel" },
        { icon: FileText, label: "PDF" },
        { icon: FileJson, label: "JSON" },
      ].map(({ icon: Icon, label }) => (
        <div key={label} className="bg-surface-2 rounded-lg px-3 py-2 text-[11px] text-muted-foreground flex items-center gap-1.5">
          <Icon className="w-3.5 h-3.5 shrink-0" />
          {label}
        </div>
      ))}
    </div>
    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
      <Download className="w-3 h-3" /> <span>One-click download</span>
      <Share2 className="w-3 h-3 ml-2" /> <span>Share link</span>
    </div>
  </div>
);

/* ── Dashboard Preview (for Hero) ────────────────────────────── */
const DashboardPreview = () => (
  <div className="glass-card p-5 space-y-3">
    <div className="flex items-center gap-3 mb-2">
      <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center"><BarChart3 className="w-4 h-4 text-primary" /></div>
      <div>
        <p className="text-sm font-semibold text-foreground">Live Dashboard</p>
        <p className="text-[10px] text-muted-foreground">Updated 2 min ago</p>
      </div>
    </div>
    {[
      { name: "Dior Sauvage EDP", price: "125.00 €", change: -7.4 },
      { name: "Bleu de Chanel", price: "98.50 €", change: -3.2 },
      { name: "Tom Ford Oud Wood", price: "189.00 €", change: 2.1 },
    ].map((p) => (
      <div key={p.name} className="flex items-center justify-between py-2 border-b border-border last:border-0">
        <span className="text-xs text-foreground">{p.name}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-foreground price-display">{p.price}</span>
          <span className={`text-[10px] font-semibold ${p.change < 0 ? "text-success" : "text-destructive"}`}>
            {p.change < 0 ? "↓" : "↑"} {Math.abs(p.change)}%
          </span>
        </div>
      </div>
    ))}
  </div>
);

/* ── Tab Previews ─────────────────────────────────────────────── */
const DashboardTabContent = () => (
  <div className="glass-card overflow-hidden">
    <div className="grid grid-cols-4 gap-0 text-[11px] font-semibold text-muted-foreground border-b border-border px-4 py-3">
      <span>Product</span><span>Store</span><span className="text-right">Price</span><span className="text-right">Change</span>
    </div>
    {[
      { product: "Dior Sauvage EDP 100ml", store: "Douglas", price: "125.00 €", change: "-7.4%", down: true },
      { product: "Bleu de Chanel EDT 50ml", store: "Notino", price: "72.90 €", change: "-3.2%", down: true },
      { product: "Hugo Boss Bottled EDP", store: "1a.lv", price: "62.90 €", change: "+1.5%", down: false },
      { product: "Tom Ford Oud Wood 50ml", store: "Douglas", price: "189.00 €", change: "-12.0%", down: true },
      { product: "YSL La Nuit 100ml", store: "Notino", price: "88.50 €", change: "+0.8%", down: false },
    ].map((r, i) => (
      <div key={i} className="grid grid-cols-4 gap-0 text-xs px-4 py-3 border-b border-border/50 last:border-0 hover:bg-surface-2/50 transition-colors">
        <span className="text-foreground font-medium truncate pr-2">{r.product}</span>
        <span className="text-muted-foreground">{r.store}</span>
        <span className="text-right text-foreground font-semibold price-display">{r.price}</span>
        <span className={`text-right font-semibold ${r.down ? "text-success" : "text-destructive"}`}>{r.change}</span>
      </div>
    ))}
  </div>
);

const ChartsTabContent = () => (
  <div className="glass-card p-6">
    <div className="flex items-center justify-between mb-4">
      <p className="text-sm font-semibold text-foreground">Dior Sauvage EDP — 90 Day Trend</p>
      <div className="flex gap-1">
        {["1M", "3M", "6M"].map((p) => (
          <span key={p} className={`px-2.5 py-1 rounded-full text-[10px] font-semibold ${p === "3M" ? "bg-primary text-primary-foreground" : "bg-surface-2 text-muted-foreground"}`}>{p}</span>
        ))}
      </div>
    </div>
    <svg viewBox="0 0 400 120" className="w-full" fill="none">
      <defs>
        <linearGradient id="lgFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="hsl(263,70%,58%)" stopOpacity="0.15" />
          <stop offset="100%" stopColor="hsl(263,70%,58%)" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="lgStroke" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="hsl(263,70%,58%)" />
          <stop offset="100%" stopColor="hsl(187,94%,43%)" />
        </linearGradient>
      </defs>
      <path d="M0 90 Q30 85 60 75 T120 60 T180 55 T240 40 T300 45 T360 30 T400 35" stroke="url(#lgStroke)" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M0 90 Q30 85 60 75 T120 60 T180 55 T240 40 T300 45 T360 30 T400 35 V120 H0Z" fill="url(#lgFill)" />
    </svg>
    <div className="flex justify-between mt-2 text-[10px] text-muted-foreground">
      <span>Dec 22</span><span>Jan 15</span><span>Feb 8</span><span>Mar 1</span><span>Mar 22</span>
    </div>
  </div>
);

const AlertsTabContent = () => (
  <div className="glass-card p-5 space-y-3">
    {[
      { icon: ArrowDown, text: "Dior Sauvage dropped to 125.00 € at Douglas", time: "3 min ago", color: "text-success" },
      { icon: ArrowDown, text: "Bleu de Chanel dropped to 72.90 € at Notino", time: "1 hour ago", color: "text-success" },
      { icon: ArrowUp, text: "Hugo Boss Bottled rose to 64.90 € at 1a.lv", time: "5 hours ago", color: "text-destructive" },
      { icon: ArrowDown, text: "Tom Ford Oud Wood dropped to 189.00 € at Douglas", time: "1 day ago", color: "text-success" },
    ].map((a, i) => (
      <div key={i} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
        <div className={`mt-0.5 w-6 h-6 rounded-full flex items-center justify-center ${a.color === "text-success" ? "bg-success/10" : "bg-destructive/10"}`}>
          <a.icon className={`w-3 h-3 ${a.color}`} />
        </div>
        <div className="flex-1">
          <p className="text-xs text-foreground">{a.text}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">{a.time}</p>
        </div>
      </div>
    ))}
  </div>
);

/* ── Features Data ────────────────────────────────────────────── */
const featureGrid = [
  { icon: TrendingDown, title: "Track Price Drops", desc: "Get instant alerts when prices fall across all monitored stores.", preview: PriceDropCard },
  { icon: Store, title: "Compare Across Stores", desc: "See side-by-side pricing from Douglas, Notino, 1a.lv and more.", preview: ComparisonTable },
  { icon: Bot, title: "AI-Powered Insights", desc: "Ask natural questions about pricing trends and get instant answers.", preview: AiChatPreview },
  { icon: Download, title: "Export & Share", desc: "Download price history in CSV, Excel, PDF or JSON format.", preview: ExportPreview },
];

const bottomFeatures = [
  { icon: Shield, title: "Reliable & Accurate", desc: "Prices are scanned twice daily across all stores. You always see fresh, verified data." },
  { icon: Zap, title: "Lightning Fast", desc: "Sub-second search and real-time updates. No waiting, no refreshing." },
  { icon: Eye, title: "Full Transparency", desc: "Complete price history with no hidden data. See every change, every day." },
  { icon: Bell, title: "Smart Notifications", desc: "Telegram, SMS, or email — choose how and when you want to be notified." },
];

/* ── Page ─────────────────────────────────────────────────────── */
const Index = () => {
  const navigate = useNavigate();
  const [authOpen, setAuthOpen] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState<null | 1 | 2>(null);

  return (
    <div className="relative min-h-screen bg-background overflow-x-hidden">
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} onRegister={() => { setAuthOpen(false); setOnboardingStep(1); }} onSignIn={() => navigate("/dashboard")} />
      <OnboardingModal open={onboardingStep === 1} onClose={() => setOnboardingStep(null)} onNext={() => setOnboardingStep(2)} />
      <OnboardingStep2 open={onboardingStep === 2} onClose={() => { setOnboardingStep(null); navigate("/dashboard", { state: { showTutorial: true } }); }} onBack={() => setOnboardingStep(1)} />

      {/* ─── Header ─── */}
      <header className="sticky top-0 z-50 h-16 flex items-center justify-between px-5 md:px-10 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <img src={logoImg} alt="MarketPulse" className="h-9 w-auto shrink-0" />
            <span className="font-display text-xl font-bold text-foreground">
              Market<span className="text-primary">Pulse</span>
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-6">
            {["Use Cases", "Pricing", "Docs"].map((l) => (
              <a key={l} href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">{l}</a>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setAuthOpen(true)} className="hidden sm:inline-flex items-center justify-center text-sm font-medium border border-primary text-primary rounded-button px-4 py-2 transition-all hover:bg-primary/10">
            Sign In
          </button>
          <button onClick={() => setAuthOpen(true)} className="btn-primary text-sm px-5 py-2">
            Get Started
          </button>
        </div>
      </header>

      {/* ─── Hero ─── */}
      <section className="relative z-10 max-w-7xl mx-auto px-5 md:px-10 pt-20 md:pt-32 pb-20">
        {/* Background blobs */}
        <div
          className="hero-blob w-[500px] h-[500px] top-[-120px] right-[-100px] opacity-[0.09]"
          style={{ background: "hsl(263 70% 58%)" }}
        />
        <div
          className="hero-blob w-[400px] h-[400px] bottom-[-80px] left-[-80px] opacity-[0.07]"
          style={{ background: "hsl(187 94% 43%)" }}
        />

        {/* 60 / 40 asymmetric grid — left col wider */}
        <div className="relative z-10 grid md:grid-cols-[1fr_0.7fr] gap-10 items-center">
          <div className="animate-fade-in">
            {/* Top badge */}
            <div className="inline-flex items-center gap-2 border border-primary/30 rounded-full px-4 py-1.5 mb-5">
              <span className="text-primary text-sm">✦</span>
              <span className="text-xs text-muted-foreground font-medium">Latvian perfume price intelligence</span>
            </div>

            {/* Stats bar */}
            <div className="flex flex-wrap items-center gap-2 mb-6">
              {[
                { dot: true, text: "5 stores monitored" },
                { dot: false, text: "1,200+ perfumes" },
                { dot: false, text: "2× daily scan" },
              ].map((s, i) => (
                <span key={i} className="badge-pill">
                  {s.dot && <span className="dot" />}
                  {s.text}
                </span>
              ))}
            </div>

            <h1 className="font-display text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.1] text-foreground">
              Stop guessing
              <br />
              <span className="gradient-text">prices.</span>
              <br />
              Start knowing them.
            </h1>
            <p className="mt-6 text-base text-muted-foreground max-w-md leading-relaxed">
              Douglas dropped Dior Sauvage by 8.5% last Tuesday. Did you know? MarketPulse would have told you the moment it happened.
            </p>
            <div className="flex items-center gap-4 mt-8">
              <button onClick={() => setAuthOpen(true)} className="btn-primary text-base px-8 py-3.5">
                Start for Free <ChevronRight className="w-4 h-4 ml-1 inline" />
              </button>
              <button onClick={() => setAuthOpen(true)} className="inline-flex items-center justify-center text-sm font-medium border border-border text-foreground rounded-button px-6 py-3.5 transition-all hover:bg-surface-2">
                See Demo
              </button>
            </div>

            {/* Trust badges */}
            <div className="flex items-center gap-4 mt-5">
              <span className="check-badge">
                <Check className="w-3.5 h-3.5" />
                No credit card required
              </span>
              <span className="check-badge">
                <Check className="w-3.5 h-3.5" />
                Free for 5 products
              </span>
            </div>
          </div>

          {/* Right col — card + floating toast */}
          <div className="hidden md:block animate-fade-in relative" style={{ animationDelay: "0.3s" }}>
            {/* Floating live toast — top-right corner */}
            <div
              className="absolute -top-4 -right-4 z-20 animate-fade-in"
              style={{ animationDelay: "1.2s" }}
            >
              <div className="glass-card px-3.5 py-2.5 flex items-center gap-2.5 shadow-glow min-w-0">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-success/15 shrink-0">
                  <ArrowDown className="w-3 h-3 text-success" />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-foreground whitespace-nowrap">Dior Sauvage ↓ 8.5%</p>
                  <p className="text-[10px] text-muted-foreground">Douglas.lv · just now</p>
                </div>
                <span className="dot ml-1 shrink-0" style={{ background: "hsl(160 84% 39%)", width: 6, height: 6, borderRadius: '50%', display: 'inline-block', animation: 'pulse-dot 2s ease-in-out infinite' }} />
              </div>
            </div>
            <DashboardPreview />
          </div>
        </div>
      </section>

      {/* ─── Stats Strip ─── */}
      <Section className="stats-strip">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-border/50">
            <StatItem value={5} suffix="+" label="Stores monitored" />
            <StatItem value={1200} suffix="+" label="Perfumes tracked" />
            <StatItem value={4800} suffix="+" label="Price checks / day" />
            <StatItem value={8} suffix="%" label="Avg. savings found" />
          </div>
        </div>
      </Section>

      {/* ─── Meet MarketPulse ─── */}
      <Section className="py-24 px-5 md:px-10">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold tracking-widest uppercase text-primary mb-3">Why MarketPulse</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground">Meet MarketPulse</h2>
            <p className="mt-4 text-muted-foreground max-w-xl mx-auto">Everything you need to track perfume prices intelligently.</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-6">
            {featureGrid.map((f) => (
              <div key={f.title} className="feature-card p-7">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <f.icon className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-display text-base font-bold text-foreground">{f.title}</h3>
                    <p className="text-xs text-muted-foreground">{f.desc}</p>
                  </div>
                </div>
                <f.preview />
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ─── Built to Work for You ─── */}
      <Section className="py-24 px-5 md:px-10">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground">
                Built to Work
                <br />
                <span className="gradient-text">for You</span>
              </h2>
              <p className="mt-4 text-muted-foreground leading-relaxed max-w-md">
                Whether you're a perfume enthusiast or a reseller, MarketPulse gives you the tools to make smarter purchasing decisions every day.
              </p>
              <ul className="mt-6 space-y-3">
                {["Monitor 5+ stores simultaneously", "AI-powered price predictions", "Instant alerts via Telegram & email", "Historical data spanning 12+ months"].map((item) => (
                  <li key={item} className="flex items-center gap-3 text-sm text-foreground">
                    <span className="w-5 h-5 rounded-full bg-success/10 flex items-center justify-center text-success text-xs">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="glass-card p-6">
              <div className="flex items-center gap-2 mb-4">
                <MessageSquare className="w-4 h-4 text-primary" />
                <span className="text-xs font-semibold text-foreground">Smart Notifications</span>
              </div>
              {[
                { text: "🔔 Dior Sauvage dropped 8.5% at Douglas", time: "Just now", highlight: true },
                { text: "📊 Weekly digest: 3 price drops in your watchlist", time: "2 hours ago", highlight: false },
                { text: "🔔 Bleu de Chanel at historic low (72.90 €)", time: "Yesterday", highlight: false },
              ].map((n, i) => (
                <div key={i} className={`flex items-center justify-between py-3 border-b border-border/50 last:border-0 ${n.highlight ? "bg-primary/5 -mx-2 px-2 rounded-lg" : ""}`}>
                  <span className="text-xs text-foreground">{n.text}</span>
                  <span className="text-[10px] text-muted-foreground ml-3 shrink-0">{n.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* ─── Your Price Dashboard ─── */}
      <Section className="py-24 px-5 md:px-10">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground">Your Price Dashboard</h2>
            <p className="mt-4 text-muted-foreground">A glimpse of what's waiting for you inside.</p>
          </div>
          <Tabs defaultValue="dashboard" className="w-full">
            <TabsList className="mx-auto flex w-fit bg-surface-2 rounded-full p-1 mb-8">
              <TabsTrigger value="dashboard" className="rounded-full px-5 py-2 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Dashboard</TabsTrigger>
              <TabsTrigger value="charts" className="rounded-full px-5 py-2 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Charts</TabsTrigger>
              <TabsTrigger value="alerts" className="rounded-full px-5 py-2 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Alerts</TabsTrigger>
            </TabsList>
            <TabsContent value="dashboard"><DashboardTabContent /></TabsContent>
            <TabsContent value="charts"><ChartsTabContent /></TabsContent>
            <TabsContent value="alerts"><AlertsTabContent /></TabsContent>
          </Tabs>
        </div>
      </Section>

      {/* ─── Bottom Features ─── */}
      <Section className="py-24 px-5 md:px-10">
        <div className="max-w-7xl mx-auto grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {bottomFeatures.map((f) => (
            <div key={f.title} className="feature-card p-6 text-center">
              <div className="inline-flex items-center justify-center w-11 h-11 rounded-card bg-primary/10 mb-4">
                <f.icon className="w-5 h-5 text-primary" />
              </div>
              <h3 className="font-display text-base font-bold text-foreground mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ─── CTA ─── */}
      <Section className="py-24 px-5 md:px-10">
        <div className="max-w-2xl mx-auto text-center">
          <div className="cta-card">
            <div className="cta-glow" />
            <div className="relative z-10">
              <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground">The market doesn't wait.<br />Neither should you.</h2>
              <p className="mt-4 text-muted-foreground max-w-md mx-auto">Every hour you don't track prices is an hour someone else is buying smarter than you.</p>
              <button onClick={() => setAuthOpen(true)} className="btn-primary text-base px-10 py-4 mt-8">
                Get Started — It's Free <ChevronRight className="w-4 h-4 ml-1 inline" />
              </button>
              <div className="flex items-center justify-center gap-6 mt-5">
                <span className="check-badge">
                  <Check className="w-3.5 h-3.5" />
                  No credit card
                </span>
                <span className="check-badge">
                  <Check className="w-3.5 h-3.5" />
                  Free forever plan
                </span>
                <span className="check-badge">
                  <Check className="w-3.5 h-3.5" />
                  Cancel anytime
                </span>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* ─── Footer ─── */}
      <footer className="border-t border-border/50 py-8 px-5 md:px-10">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <span>© 2026 MarketPulse</span>
          <div className="flex gap-6">
            <a href="#" className="hover:text-foreground transition-colors">Privacy</a>
            <a href="#" className="hover:text-foreground transition-colors">Terms</a>
            <a href="#" className="hover:text-foreground transition-colors">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
