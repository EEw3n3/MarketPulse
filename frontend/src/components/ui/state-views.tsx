import { RefreshCw, AlertCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// ── LoadingState ──────────────────────────────────────────────────────────────

interface LoadingStateProps {
  label?: string;
  /** Tailwind height class, e.g. "h-[200px]". Ignored when fullscreen=true. */
  height?: string;
  /** Renders as h-screen bg-background (for page-level transitions). */
  fullscreen?: boolean;
  className?: string;
}

export function LoadingState({
  label = "Loading",
  height = "h-[200px]",
  fullscreen = false,
  className,
}: LoadingStateProps) {
  if (fullscreen) {
    return (
      <div className={cn("h-screen flex flex-col items-center justify-center bg-background gap-3", className)}>
        <RefreshCw className="animate-spin text-muted-foreground" size={18} />
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      </div>
    );
  }
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 border border-border rounded-md bg-surface/40",
        height,
        className
      )}
    >
      <RefreshCw className="animate-spin text-muted-foreground" size={16} />
      <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
    </div>
  );
}

// ── ErrorState ────────────────────────────────────────────────────────────────

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  /** Renders as h-screen bg-background (for page-level transitions). */
  fullscreen?: boolean;
  className?: string;
}

export function ErrorState({
  message,
  onRetry,
  retryLabel = "Try again",
  fullscreen = false,
  className,
}: ErrorStateProps) {
  if (fullscreen) {
    return (
      <div className={cn("h-screen flex flex-col items-center justify-center bg-background gap-3 px-6 text-center", className)}>
        <AlertCircle className="text-destructive" size={22} />
        <p className="text-foreground text-[13px]">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-[12px] text-muted-foreground hover:text-foreground underline underline-offset-2 mt-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
          >
            {retryLabel}
          </button>
        )}
      </div>
    );
  }
  return (
    <div
      className={cn(
        "border border-border rounded-md bg-surface/40 px-6 py-8 text-center flex flex-col items-center gap-2",
        className
      )}
    >
      <AlertCircle className="text-destructive" size={16} />
      <p className="text-[13px] text-foreground">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-[12px] text-muted-foreground hover:text-foreground underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}

// ── EmptyState ────────────────────────────────────────────────────────────────

interface EmptyStateProps {
  message: string;
  description?: string;
  icon?: LucideIcon;
  className?: string;
}

export function EmptyState({ message, description, icon: Icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "border border-border rounded-md bg-surface/40 px-6 py-8 text-center flex flex-col items-center gap-2",
        className
      )}
    >
      {Icon && <Icon size={18} className="text-muted-foreground/40" strokeWidth={1.5} />}
      <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{message}</p>
      {description && (
        <p className="text-[12px] text-muted-foreground/70 mt-0.5">{description}</p>
      )}
    </div>
  );
}
