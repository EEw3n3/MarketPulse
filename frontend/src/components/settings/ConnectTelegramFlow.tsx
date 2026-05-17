import { useEffect, useRef, useState } from "react";
import { Send, Loader2, AlertTriangle, ExternalLink, Copy, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Status = "idle" | "modal" | "waiting" | "timeout";

/**
 * Derive the Telegram Web URL for the actual bot configured on the server.
 * The bot username can differ between environments (dev/staging/prod), so we
 * MUST extract it from the deeplink the backend just generated — hardcoding
 * "@MarketPulseBot" sends users to Web Telegram's fuzzy-match, which can open
 * a totally different bot from the user's chat history.
 */
function deriveWebTelegramUrl(deepLink: string): string {
  // deepLink form: https://t.me/<BotUsername>?start=mp_<token>
  const m = deepLink.match(/t\.me\/([A-Za-z0-9_]+)/i);
  const username = m ? m[1] : "";
  return username
    ? `https://web.telegram.org/k/#@${username}`
    : "https://web.telegram.org/k/";
}

/**
 * Telegram connect flow with explicit confirmation.
 *
 * The flow used to redirect straight to `t.me/MarketPulseBot?start=...`, which
 * caused a critical UX bug: if the laptop's Telegram app was signed in to a
 * different account than the one logged into MarketPulse, the bot would link
 * the WRONG chat to the user. Now we show a modal first that:
 *   1) Tells the user which MarketPulse account is about to be linked
 *   2) Offers TWO ways to open the bot — native app or Telegram Web
 *   3) Exposes the deeplink token so the user can paste it manually if Web
 *      doesn't auto-pass the `start=` parameter
 */
export default function ConnectTelegramFlow() {
  const { user, refreshUser } = useAuth();
  const [status, setStatus] = useState<Status>("idle");
  const [deepLink, setDeepLink] = useState<string | null>(null);
  const [startToken, setStartToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const startConnect = async () => {
    setLoading(true);
    try {
      const { deep_link } = await api.connectTelegram();
      setDeepLink(deep_link);
      // Extract the `start=<token>` part so the user can paste it into Web Telegram.
      const m = deep_link.match(/[?&]start=([^&]+)/);
      setStartToken(m ? `/start ${m[1]}` : null);
      setStatus("modal");
    } catch {
      toast.error("Failed to generate Telegram link. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const beginPolling = () => {
    setStatus("waiting");
    let ticks = 0;
    intervalRef.current = setInterval(async () => {
      ticks++;
      try {
        await refreshUser();
      } catch {
        // ignore — keep polling
      }
      if (ticks >= 20) {
        if (intervalRef.current) clearInterval(intervalRef.current);
        intervalRef.current = null;
        setStatus("timeout");
      }
    }, 3000);
  };

  const openInApp = () => {
    if (!deepLink) return;
    window.open(deepLink, "_blank");
    beginPolling();
  };

  const openInWeb = () => {
    if (!deepLink) return;
    window.open(deriveWebTelegramUrl(deepLink), "_blank");
    beginPolling();
  };

  const copyToken = async () => {
    if (!startToken) return;
    // navigator.clipboard only works in secure contexts (HTTPS or localhost).
    // The prod site runs on plain HTTP, so we must fall back to the legacy
    // execCommand("copy") path with a hidden textarea.
    try {
      if (
        typeof navigator !== "undefined" &&
        navigator.clipboard &&
        window.isSecureContext
      ) {
        await navigator.clipboard.writeText(startToken);
        toast.success("Copied to clipboard");
        return;
      }
      const ta = document.createElement("textarea");
      ta.value = startToken;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, ta.value.length);
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      if (ok) {
        toast.success("Copied to clipboard");
      } else {
        toast.error("Couldn't copy — select the text and press Ctrl+C");
      }
    } catch {
      toast.error("Couldn't copy — select the text and press Ctrl+C");
    }
  };

  // Watch for successful connection while polling
  useEffect(() => {
    if (status === "waiting" && user?.preferences?.telegram_chat_id) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setStatus("idle");
      toast.success("Telegram connected");
    }
  }, [user?.preferences?.telegram_chat_id, status]);

  return (
    <>
      {status === "idle" && (
        <button
          onClick={startConnect}
          disabled={loading}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border text-[12px] text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors disabled:opacity-60"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} strokeWidth={1.75} />}
          Connect Telegram
        </button>
      )}

      {status === "waiting" && (
        <div className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
          <Loader2 size={13} className="animate-spin shrink-0" />
          <span>Waiting for Telegram confirmation…</span>
          <button
            onClick={() => {
              if (intervalRef.current) clearInterval(intervalRef.current);
              setStatus("idle");
            }}
            className="ml-1 underline underline-offset-2 hover:text-foreground transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {status === "timeout" && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-[12.5px] text-amber-500">
            <AlertTriangle size={13} className="shrink-0" />
            <span>Timed out. Open the link in Telegram and send /start.</span>
          </div>
          <button
            onClick={() => setStatus("idle")}
            className="self-start text-[12px] text-muted-foreground underline underline-offset-2 hover:text-foreground transition-colors"
          >
            Try again
          </button>
        </div>
      )}

      <Dialog open={status === "modal"} onOpenChange={(o) => !o && setStatus("idle")}>
        <DialogContent className="max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Link Telegram to your account</DialogTitle>
            <DialogDescription>
              You're about to link a Telegram chat to:{" "}
              <span className="text-foreground font-semibold">{user?.email}</span>
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-3 text-[12.5px]">
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-md border border-amber-500/30 bg-amber-500/[0.07]">
              <AlertCircle size={14} className="text-amber-500 shrink-0 mt-0.5" />
              <p className="text-amber-200/90 leading-relaxed">
                The bot binds <strong>whichever Telegram chat opens it</strong> to{" "}
                <strong>{user?.email}</strong>. Make sure the Telegram you open is signed
                into the correct account, otherwise the wrong chat will receive your alerts.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <button
                onClick={openInApp}
                className="inline-flex items-center justify-between gap-2 h-10 px-3 rounded-md border border-primary bg-primary/10 text-foreground text-[13px] hover:bg-primary/20 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Send size={14} />
                  Open in Telegram app
                </span>
                <ExternalLink size={12} className="text-muted-foreground" />
              </button>

              <button
                onClick={openInWeb}
                className="inline-flex items-center justify-between gap-2 h-10 px-3 rounded-md border border-border text-foreground text-[13px] hover:border-muted-foreground transition-colors"
              >
                <span className="flex items-center gap-2">
                  <ExternalLink size={14} />
                  Open in Telegram Web
                </span>
                <ExternalLink size={12} className="text-muted-foreground" />
              </button>
            </div>

            {startToken && (
              <div className="flex flex-col gap-1.5 px-3 py-2.5 rounded-md border border-border bg-surface-2">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Manual command — click field, press Ctrl+C, paste to bot
                </span>
                <div className="flex items-center gap-2">
                  <input
                    readOnly
                    value={startToken}
                    onFocus={(e) => e.currentTarget.select()}
                    onClick={(e) => e.currentTarget.select()}
                    className="flex-1 font-mono text-[11.5px] text-foreground bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:border-primary"
                  />
                  <button
                    onClick={copyToken}
                    className="inline-flex items-center gap-1 h-7 px-2 rounded text-[10.5px] font-mono border border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors"
                  >
                    <Copy size={11} />
                    Copy
                  </button>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <button
              onClick={() => setStatus("idle")}
              className="text-[12.5px] text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
