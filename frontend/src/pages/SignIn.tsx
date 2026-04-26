import { useState } from "react";
import { useNavigate, Link, Navigate } from "react-router-dom";
import { Eye, EyeOff, AlertCircle, ArrowLeft, Check } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import logoImg from "@/assets/logo.png";

const BENEFITS = [
  "Resume monitoring on 5 Latvian retailers",
  "Access your saved price alerts and history",
  "Pick up where your dashboard left off",
];

export default function SignIn() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setError(msg.includes("401") ? "Incorrect email or password" : "Something went wrong. Try again.");
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
        {/* Ambient glow */}
        <div
          aria-hidden
          className="absolute left-[-120px] top-1/2 -translate-y-1/2 w-[520px] h-[520px] rounded-full pointer-events-none"
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
            <span className="text-primary">01</span> · <span className="text-foreground">Access</span>
          </span>

          <h1 className="font-['Inter'] font-semibold text-foreground text-[36px] leading-[1.1] tracking-[-0.02em]">
            Sign back in.
            <br />
            Prices kept moving.
          </h1>

          <ul className="mt-10 space-y-3.5">
            {BENEFITS.map((b) => (
              <li key={b} className="flex items-start gap-3 text-[14px] text-muted-foreground">
                <Check className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex items-center gap-6 text-[11px] text-muted-foreground font-mono">
          <span>336 products tracked</span>
          <span className="w-px h-3 bg-border" />
          <span>5 retailers</span>
          <span className="w-px h-3 bg-border" />
          <span>2× daily refresh</span>
        </div>
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
            New here?{" "}
            <Link to="/register" className="text-foreground hover:underline font-medium">
              Create account
            </Link>
          </p>
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-sm">
            <h2 className="font-['Inter'] font-semibold text-foreground text-[28px] leading-[1.15] tracking-[-0.01em] mb-2">
              Sign in
            </h2>
            <p className="text-[14px] text-muted-foreground mb-8">
              Enter your email and password to continue.
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
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                  className="w-full bg-surface border border-border rounded-md px-3.5 py-2.5 text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-[0.14em]">
                    Password
                  </label>
                  <button
                    type="button"
                    className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Forgot?
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full bg-surface border border-border rounded-md px-3.5 py-2.5 pr-10 text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors [&::-ms-reveal]:hidden [&::-webkit-credentials-auto-fill-button]:hidden"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-foreground text-background rounded-md py-2.5 text-[14px] font-medium hover:bg-foreground/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>

            <p className="sm:hidden text-center text-[13px] text-muted-foreground mt-8">
              New here?{" "}
              <Link to="/register" className="text-foreground hover:underline font-medium">
                Create account
              </Link>
            </p>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground font-mono text-center lg:text-left">
          marketpulse.lv · Secured with JWT · Never shared with retailers
        </p>
      </main>
    </div>
  );
}
