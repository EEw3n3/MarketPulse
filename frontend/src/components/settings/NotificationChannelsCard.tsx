import { useState } from "react";
import { Check, Mail, Send, Unlink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import ConnectTelegramFlow from "./ConnectTelegramFlow";

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
      {children}
    </span>
  );
}

export default function NotificationChannelsCard() {
  const { user, updatePreferences, refreshUser } = useAuth();
  const prefs = user?.preferences;

  const channels = prefs?.notification_channels ?? [];
  const [emailOn, setEmailOn] = useState(channels.includes("email"));
  const [telegramOn, setTelegramOn] = useState(channels.includes("telegram"));
  const [threshold, setThreshold] = useState(
    String(prefs?.notification_threshold_percent ?? 5)
  );
  const [saving, setSaving] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const selected: ("email" | "telegram")[] = [];
      if (emailOn) selected.push("email");
      if (telegramOn && prefs?.telegram_chat_id) selected.push("telegram");
      await updatePreferences({
        notification_channels: selected,
        notification_threshold_percent: Number(threshold),
      });
      toast.success("Notification settings saved");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await api.disconnectTelegram();
      await refreshUser();
      setTelegramOn(false);
      toast.success("Telegram disconnected");
    } catch {
      toast.error("Failed to disconnect Telegram");
    } finally {
      setDisconnecting(false);
    }
  };

  const telegramConnected = Boolean(prefs?.telegram_chat_id);

  return (
    <div className="flex flex-col gap-5">
      {/* Email row */}
      <div className="flex items-start justify-between gap-4 py-4 border-b border-border first:pt-0">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-md bg-surface-2 border border-border flex items-center justify-center shrink-0 mt-0.5">
            <Mail size={14} className="text-muted-foreground" strokeWidth={1.75} />
          </div>
          <div className="flex flex-col gap-0.5">
            <p className="text-[13px] text-foreground font-medium">Email</p>
            <p className="text-[11.5px] text-muted-foreground">
              {user?.email}
              <span className="ml-2 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-[hsl(var(--success))] border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/[0.08] px-1.5 py-0.5 rounded">
                <Check size={8} strokeWidth={2.5} />
                Verified
              </span>
            </p>
          </div>
        </div>
        <Switch
          checked={emailOn}
          onCheckedChange={setEmailOn}
          className="data-[state=checked]:bg-primary mt-0.5 shrink-0"
        />
      </div>

      {/* Telegram row */}
      <div className="flex items-start justify-between gap-4 py-4 border-b border-border">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-md bg-surface-2 border border-border flex items-center justify-center shrink-0 mt-0.5">
            <Send size={14} className="text-muted-foreground" strokeWidth={1.75} />
          </div>
          <div className="flex flex-col gap-1.5">
            <p className="text-[13px] text-foreground font-medium">Telegram</p>
            {telegramConnected ? (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-[hsl(var(--success))]">
                  <Check size={10} strokeWidth={2.5} />
                  Connected
                </span>
                <button
                  onClick={handleDisconnect}
                  disabled={disconnecting}
                  className="inline-flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-destructive transition-colors"
                >
                  {disconnecting ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <Unlink size={11} strokeWidth={1.75} />
                  )}
                  Disconnect
                </button>
              </div>
            ) : (
              <ConnectTelegramFlow />
            )}
          </div>
        </div>
        {telegramConnected && (
          <Switch
            checked={telegramOn}
            onCheckedChange={setTelegramOn}
            className="data-[state=checked]:bg-primary mt-0.5 shrink-0"
          />
        )}
      </div>

      {/* Threshold */}
      <div className="flex flex-col gap-1.5 pt-1">
        <FieldLabel>Alert threshold</FieldLabel>
        <p className="text-[11.5px] text-muted-foreground -mt-0.5 mb-1">
          Minimum price change to trigger a notification.
        </p>
        <Select value={threshold} onValueChange={setThreshold}>
          <SelectTrigger className="bg-surface border-border h-9 text-[13px] focus:ring-1 focus:ring-primary focus:border-primary max-w-[280px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-background border-border">
            <SelectItem value="1">1% — every move</SelectItem>
            <SelectItem value="3">3% — high sensitivity</SelectItem>
            <SelectItem value="5">5% — recommended</SelectItem>
            <SelectItem value="10">10% — medium</SelectItem>
            <SelectItem value="20">20% — major drops only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Save */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="self-start h-9 px-4 rounded-md bg-foreground text-background text-[12.5px] font-medium hover:bg-foreground/90 disabled:opacity-50 transition-colors flex items-center gap-2"
      >
        {saving && <Loader2 size={13} className="animate-spin" />}
        Save
      </button>
    </div>
  );
}
