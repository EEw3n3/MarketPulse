import { useEffect, useRef, useState } from "react";
import { Send, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type Status = "idle" | "waiting" | "timeout";

export default function ConnectTelegramFlow() {
  const { user, refreshUser } = useAuth();
  const [status, setStatus] = useState<Status>("idle");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const onConnect = async () => {
    try {
      const { deep_link } = await api.connectTelegram();
      window.open(deep_link, "_blank");
      setStatus("waiting");

      let ticks = 0;
      intervalRef.current = setInterval(async () => {
        ticks++;
        try {
          await refreshUser();
        } catch {
          // ignore refresh errors — keep polling
        }
        // refreshUser updates user in context; check on next render via effect
        if (ticks >= 20) {
          clearInterval(intervalRef.current!);
          intervalRef.current = null;
          setStatus("timeout");
        }
      }, 3000);
    } catch {
      toast.error("Failed to generate Telegram link. Try again.");
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

  if (status === "waiting") {
    return (
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
    );
  }

  if (status === "timeout") {
    return (
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
    );
  }

  return (
    <button
      onClick={onConnect}
      className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border text-[12px] text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors"
    >
      <Send size={12} strokeWidth={1.75} />
      Connect Telegram
    </button>
  );
}
