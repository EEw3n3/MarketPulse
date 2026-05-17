import { useState } from "react";
import { useNavigate, Link, Navigate } from "react-router-dom";
import { Eye, EyeOff, AlertCircle, ArrowLeft, Radio, Database, Bell } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import logoImg from "@/assets/logo.png";

const PILLARS = [
  { icon: Database, label: "5 retailers", sub: "Douglas · Notino · Makeup · 1a · 220" },
  { icon: Radio, label: "2× daily", sub: "Refresh every 12 hours, no feeds" },
  { icon: Bell, label: "Free for 5 SKUs", sub: "No card. 12 months of history." },
];

export default function Register() {
  const { register, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, fullName || undefined);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      // fetchApi formats errors as: "API Error: <status> <detail-or-statusText>"
      const m = msg.match(/^API Error:\s*(\d+)\s*(.*)$/);
      const status = m ? Number(m[1]) : 0;
      const detail = m ? m[2].trim() : "";
      if (status === 409) {
        setError("Email already registered");
      } else if (status === 403 && detail) {
        // 403 from /auth/register = deactivated account
        setError(detail);
      } else if (detail) {
        setError(detail);
      } else {
        setError("Registration failed. Try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (user) {
    const target = user.preferences?.onboarding_completed ? "/dashboard" : "/onboarding/stores";
    return <Navigate to={target} replace />;
  }

  return (
    <div className="min-h-screen bg-background grid grid-cols-1 lg:grid-cols-2">
      {/* ═════════════════ LEFT — Brand / Editorial ═════════════════ */}
      <aside className="relative hidden lg:flex flex-col justify-between bg-surface/40 border-r border-border px-12 xl:px-16 py-10 overflow-hidden">
        <div
          aria-hidden
          className="absolute right-[-140px] top-[-140px] w-[520px] h-[520px] rounded-full pointer-events-none"
          style={{ background: "hsl(var(--primary))", filter: "blur(160px)", opacity: 0.08 }}
        />

        <div className="relative flex items-center gap-2.5">
          <img src={logoImg} alt="MarketPulse" className="h-8 w-auto" />
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            v1.0
          </span>
        </div>

        <div className="relative max-w-md">
          <span className="inline-block text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-medium mb-6">
            <span className="text-primary">00</span> · <span className="text-foreground">New account</span>
          </span>

          <h1 className="font-['Inter'] font-semibold text-foreground text-[36px] leading-[1.1] tracking-[-0.02em]">
            Start tracking
            <br />
            in under a minute.
          </h1>

          <p className="mt-5 text-[14px] text-muted-foreground leading-[1.6] max-w-sm">
            No integrations. No uploads. Pick the products you care about and MarketPulse watches the shelves
            for you.
          </p>

          <div className="mt-10 divide-y divide-border border-t border-b border-border">
            {PILLARS.map(({ icon: Icon, label, sub }) => (
              <div key={label} className="flex items-start gap-4 py-4">
                <div className="w-9 h-9 rounded-md bg-surface-2 border border-border flex items-center justify-center shrink-0">
                  <Icon className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <p className="text-[14px] font-medium text-foreground">{label}</p>
                  <p className="text-[12px] text-muted-foreground mt-0.5">{sub}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-[11px] text-muted-foreground font-mono">
          <span className="text-foreground">336 products</span> · 28 days observed · Zero retailer integrations
        </p>
      </aside>

      {/* ═════════════════ RIGHT — Form ═════════════════ */}
      <main className="flex flex-col px-6 sm:px-10 lg:px-16 py-8">
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate("/")}
            className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <div className="flex lg:hidden items-center gap-2">
            <img src={logoImg} alt="MarketPulse" className="h-7 w-auto" />
          </div>

          <p className="hidden sm:block text-[13px] text-muted-foreground">
            Already registered?{" "}
            <Link to="/signin" className="text-foreground hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-sm">
            <h2 className="font-['Inter'] font-semibold text-foreground text-[28px] leading-[1.15] tracking-[-0.01em] mb-2">
              Create account
            </h2>
            <p className="text-[14px] text-muted-foreground mb-8">
              It's free for your first five products. No card required.
            </p>

            {error && (
              <div className="flex items-center gap-2 text-[13px] text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2.5 mb-5">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-[0.14em] mb-2 block">
                  Full name <span className="normal-case text-muted-foreground/70">(optional)</span>
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoFocus
                  className="w-full bg-surface border border-border rounded-md px-3.5 py-2.5 text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                  placeholder="Ervin"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-[0.14em] mb-2 block">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full bg-surface border border-border rounded-md px-3.5 py-2.5 text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-[0.14em] mb-2 block">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    className="w-full bg-surface border border-border rounded-md px-3.5 py-2.5 pr-10 text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors [&::-ms-reveal]:hidden [&::-webkit-credentials-auto-fill-button]:hidden"
                    placeholder="Min. 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-muted-foreground mt-2">
                  At least 8 characters. Store it in a manager, not a sticky note.
                </p>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-foreground text-background rounded-md py-2.5 text-[14px] font-medium hover:bg-foreground/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Creating account…" : "Create account"}
              </button>
            </form>

            <p className="sm:hidden text-center text-[13px] text-muted-foreground mt-8">
              Already registered?{" "}
              <Link to="/signin" className="text-foreground hover:underline font-medium">
                Sign in
              </Link>
            </p>

            <p className="text-[11px] text-muted-foreground mt-6 leading-relaxed">
              By creating an account you agree to our{" "}
              <span className="text-foreground hover:underline cursor-pointer">Terms</span> and{" "}
              <span className="text-foreground hover:underline cursor-pointer">Privacy Policy</span>. We
              never sell your data.
            </p>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground font-mono text-center lg:text-left">
          marketpulse.lv · JWT-secured · GDPR-compliant
        </p>
      </main>
    </div>
  );
}
