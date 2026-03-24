import { useState, useCallback, useEffect, useRef } from "react";
import { Eye, EyeOff, Check, X, AlertCircle } from "lucide-react";

/* ── Types ────────────────────────────────────────────────────── */
type Tab = "signin" | "register";

interface FieldState {
  value: string;
  touched: boolean;
  valid: boolean;
  error: string;
}

const empty = (label: string): FieldState => ({
  value: "",
  touched: false,
  valid: false,
  error: "",
});

/* ── Password‑strength helper ─────────────────────────────────── */
const getStrength = (pw: string): { score: 0 | 1 | 2 | 3; label: string } => {
  if (!pw) return { score: 0, label: "" };
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  return (
    [
      { score: 0, label: "" },
      { score: 1, label: "Weak" },
      { score: 2, label: "Fair" },
      { score: 3, label: "Strong" },
    ] as const
  )[s];
};

const strengthColor = (score: number) =>
  ["bg-muted", "bg-destructive", "bg-yellow-500", "bg-success"][score];

/* ── Shake animation (inline style for simplicity) ────────────── */
const useShake = () => {
  const [shaking, setShaking] = useState(false);
  const trigger = useCallback(() => {
    setShaking(true);
    setTimeout(() => setShaking(false), 500);
  }, []);
  return { shaking, trigger };
};

/* ── Reusable Input ───────────────────────────────────────────── */
interface InputProps {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  valid?: boolean;
  touched?: boolean;
  error?: string;
  shaking?: boolean;
  passwordToggle?: boolean;
  placeholder?: string;
}

const FormInput = ({
  label,
  type = "text",
  value,
  onChange,
  valid,
  touched,
  error,
  shaking,
  passwordToggle,
  placeholder,
}: InputProps) => {
  const [show, setShow] = useState(false);
  const resolvedType = passwordToggle ? (show ? "text" : "password") : type;

  return (
    <div className="mb-4">
      <label className="block text-xs font-medium text-muted-foreground mb-1.5">{label}</label>
      <div className="relative">
        <input
          type={resolvedType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`
            w-full rounded-button bg-surface-2 text-foreground text-sm px-4 py-3
            border outline-none transition-all duration-200 ease-brand
            placeholder:text-muted-foreground/50
            ${
              touched && error
                ? "border-destructive focus:ring-2 focus:ring-destructive/20 bg-destructive/5"
                : touched && valid
                ? "border-success/60 focus:ring-2 focus:ring-success/20 bg-success/5"
                : "border-border focus:border-primary focus:ring-2 focus:ring-primary/20"
            }
            ${shaking ? "animate-[shake_0.4s_ease-in-out]" : ""}
          `}
        />
        {/* Right icons */}
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
          {touched && valid && <Check className="w-4 h-4 text-success transition-opacity duration-300" />}
          {touched && error && <AlertCircle className="w-4 h-4 text-destructive transition-opacity duration-300" />}
          {passwordToggle && (
            <button
              type="button"
              onClick={() => setShow(!show)}
              className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
              tabIndex={-1}
            >
              {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>
      {touched && error && (
        <p className="text-[11px] text-destructive mt-1 animate-fade-in">{error}</p>
      )}
    </div>
  );
};

/* ── Google icon (inline SVG) ─────────────────────────────────── */
const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 48 48" className="shrink-0">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
    <path fill="#FBBC05" d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19a24.01 24.01 0 0 0 0 21.56l7.98-6.19z" />
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
  </svg>
);

/* ── Main Modal ───────────────────────────────────────────────── */
interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  onRegister?: () => void;
  onSignIn?: () => void;
}

const AuthModal = ({ open, onClose, onRegister, onSignIn }: AuthModalProps) => {
  const [tab, setTab] = useState<Tab>("signin");
  const modalRef = useRef<HTMLDivElement>(null);

  /* ── Sign-In state ───── */
  const [siEmail, setSiEmail] = useState(empty("Email"));
  const [siPassword, setSiPassword] = useState(empty("Password"));
  const [remember, setRemember] = useState(false);
  const siShake = useShake();

  /* ── Register state ──── */
  const [regName, setRegName] = useState(empty("Name"));
  const [regEmail, setRegEmail] = useState(empty("Email"));
  const [regPassword, setRegPassword] = useState(empty("Password"));
  const [regConfirm, setRegConfirm] = useState(empty("Confirm"));
  const [agreeTerms, setAgreeTerms] = useState(false);
  const regShake = useShake();

  /* validators */
  const isEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

  const updateField = (
    setter: React.Dispatch<React.SetStateAction<FieldState>>,
    value: string,
    validator?: (v: string) => string
  ) => {
    const error = validator ? validator(value) : "";
    setter({ value, touched: true, valid: !error && value.length > 0, error });
  };

  /* close on Escape */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  /* close on backdrop click */
  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const handleSignIn = (e: React.FormEvent) => {
    e.preventDefault();
    const emailErr = !isEmail(siEmail.value);
    const pwErr = !siPassword.value;
    if (emailErr || pwErr) {
      siShake.trigger();
      if (emailErr)
        setSiEmail((p) => ({ ...p, touched: true, valid: false, error: "Enter a valid email" }));
      if (pwErr)
        setSiPassword((p) => ({ ...p, touched: true, valid: false, error: "Password is required" }));
      return;
    }
    // Sign in successful — go to dashboard
    onSignIn?.();
    onClose();
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    let hasErr = false;
    if (!regName.value) {
      setRegName((p) => ({ ...p, touched: true, error: "Name is required", valid: false }));
      hasErr = true;
    }
    if (!isEmail(regEmail.value)) {
      setRegEmail((p) => ({ ...p, touched: true, error: "Enter a valid email", valid: false }));
      hasErr = true;
    }
    if (regPassword.value.length < 8) {
      setRegPassword((p) => ({ ...p, touched: true, error: "Min 8 characters", valid: false }));
      hasErr = true;
    }
    if (regConfirm.value !== regPassword.value) {
      setRegConfirm((p) => ({ ...p, touched: true, error: "Passwords don't match", valid: false }));
      hasErr = true;
    }
    if (!agreeTerms) hasErr = true;
    if (hasErr) {
      regShake.trigger();
      return;
    }
    // Registration successful — trigger onboarding
    onRegister?.();
    onClose();
  };

  const strength = getStrength(regPassword.value);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center px-4 animate-fade-in"
      style={{ backdropFilter: "blur(12px)", background: "rgba(0,0,0,0.6)" }}
      onClick={handleBackdrop}
    >
      <div className="absolute inset-0 z-[-1] overflow-hidden pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/20 rounded-full blur-[100px] opacity-70" />
      </div>
      <div
        ref={modalRef}
        className="relative w-full max-w-[460px] rounded-modal overflow-hidden animate-scale-in"
        style={{
          background: "rgba(255,255,255,0.03)",
          backdropFilter: "blur(24px)",
          border: "1px solid hsl(var(--border))",
          boxShadow: "0 24px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)",
        }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="pt-8 pb-2 px-8">
          <h2 className="font-display text-2xl font-bold text-foreground text-center mb-6">
            Welcome to Market<span className="text-primary">Pulse</span>
          </h2>

          {/* Segmented Control Tabs */}
          <div className="flex bg-surface-2 p-1.5 rounded-full relative">
            {(["signin", "register"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`
                  flex-1 py-2 text-sm font-semibold rounded-full relative z-10 transition-colors duration-300
                  ${tab === t ? "text-primary-foreground" : "text-muted-foreground hover:text-foreground"}
                `}
              >
                {t === "signin" ? "Sign In" : "Register"}
              </button>
            ))}
            {/* Sliding Pill */}
            <div
              className={`
                absolute top-1.5 bottom-1.5 w-[calc(50%-6px)] bg-primary rounded-full transition-transform duration-300 ease-brand shadow-[0_0_12px_rgba(124,58,237,0.4)]
                ${tab === "signin" ? "translate-x-0" : "translate-x-[calc(100%+5px)]"}
              `}
            />
          </div>
        </div>

        {/* Body */}
        <div className="px-8 pb-8 pt-5 overflow-hidden">
          {/* ── SIGN IN ─────────────── */}
          <div
            className={`transition-all duration-300 ease-brand ${
              tab === "signin"
                ? "opacity-100 translate-x-0"
                : "opacity-0 -translate-x-4 absolute pointer-events-none"
            }`}
          >
            <form onSubmit={handleSignIn} noValidate>
              <FormInput
                label="Email"
                type="email"
                placeholder="you@example.com"
                value={siEmail.value}
                onChange={(v) => updateField(setSiEmail, v, (val) => (isEmail(val) ? "" : "Enter a valid email"))}
                valid={siEmail.valid}
                touched={siEmail.touched}
                error={siEmail.error}
                shaking={siShake.shaking}
              />
              <FormInput
                label="Password"
                placeholder="••••••••"
                value={siPassword.value}
                onChange={(v) => updateField(setSiPassword, v, (val) => (val ? "" : "Password is required"))}
                valid={siPassword.valid}
                touched={siPassword.touched}
                error={siPassword.error}
                shaking={siShake.shaking}
                passwordToggle
              />

              {/* Remember me */}
              <label className="flex items-center gap-2 mb-5 cursor-pointer select-none">
                <span
                  className={`
                    w-4 h-4 rounded-sm border flex items-center justify-center transition-all duration-200
                    ${remember ? "bg-primary border-primary" : "border-border bg-surface-2"}
                  `}
                  onClick={() => setRemember(!remember)}
                >
                  {remember && <Check className="w-3 h-3 text-primary-foreground" />}
                </span>
                <span className="text-xs text-muted-foreground" onClick={() => setRemember(!remember)}>
                  Remember me
                </span>
              </label>

              <button type="submit" className="btn-primary w-full py-3 text-sm">
                Sign In
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-3 my-5">
              <span className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground">or</span>
              <span className="flex-1 h-px bg-border" />
            </div>

            {/* Google */}
            <button
              type="button"
              className="w-full flex items-center justify-center gap-2.5 rounded-button border border-border bg-surface-2/50 text-sm font-medium text-foreground py-3 transition-all duration-200 ease-brand hover:bg-surface-2 hover:border-primary/40"
            >
              <GoogleIcon />
              Continue with Google
            </button>
          </div>

          {/* ── REGISTER ────────────── */}
          <div
            className={`transition-all duration-300 ease-brand ${
              tab === "register"
                ? "opacity-100 translate-x-0"
                : "opacity-0 translate-x-4 absolute pointer-events-none"
            }`}
          >
            <form onSubmit={handleRegister} noValidate>
              <FormInput
                label="Full Name"
                placeholder="John Doe"
                value={regName.value}
                onChange={(v) => updateField(setRegName, v, (val) => (val ? "" : "Name is required"))}
                valid={regName.valid}
                touched={regName.touched}
                error={regName.error}
                shaking={regShake.shaking}
              />
              <FormInput
                label="Email"
                type="email"
                placeholder="you@example.com"
                value={regEmail.value}
                onChange={(v) => updateField(setRegEmail, v, (val) => (isEmail(val) ? "" : "Enter a valid email"))}
                valid={regEmail.valid}
                touched={regEmail.touched}
                error={regEmail.error}
                shaking={regShake.shaking}
              />
              <FormInput
                label="Password"
                placeholder="••••••••"
                value={regPassword.value}
                onChange={(v) =>
                  updateField(setRegPassword, v, (val) => (val.length >= 8 ? "" : "Min 8 characters"))
                }
                valid={regPassword.valid}
                touched={regPassword.touched}
                error={regPassword.error}
                shaking={regShake.shaking}
                passwordToggle
              />

              {/* Strength bar */}
              {regPassword.value && (
                <div className="mb-4 -mt-2 animate-fade-in">
                  <div className="flex gap-1.5 mb-1">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                          strength.score >= i ? strengthColor(strength.score) : "bg-muted"
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-[10px] text-muted-foreground">{strength.label}</p>
                </div>
              )}

              <FormInput
                label="Confirm Password"
                placeholder="••••••••"
                value={regConfirm.value}
                onChange={(v) =>
                  updateField(setRegConfirm, v, (val) =>
                    val === regPassword.value ? "" : "Passwords don't match"
                  )
                }
                valid={regConfirm.valid}
                touched={regConfirm.touched}
                error={regConfirm.error}
                shaking={regShake.shaking}
                passwordToggle
              />

              {/* Terms checkbox */}
              <label className="flex items-start gap-2 mb-5 cursor-pointer select-none">
                <span
                  className={`
                    w-4 h-4 mt-0.5 rounded-sm border flex items-center justify-center shrink-0 transition-all duration-200
                    ${agreeTerms ? "bg-primary border-primary" : "border-border bg-surface-2"}
                  `}
                  onClick={() => setAgreeTerms(!agreeTerms)}
                >
                  {agreeTerms && <Check className="w-3 h-3 text-primary-foreground" />}
                </span>
                <span className="text-xs text-muted-foreground leading-relaxed" onClick={() => setAgreeTerms(!agreeTerms)}>
                  I agree to the{" "}
                  <a href="#" className="text-primary hover:underline">
                    Terms of Service
                  </a>
                </span>
              </label>

              <button type="submit" className="btn-primary w-full py-3 text-sm">
                Create Account
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthModal;
