import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { useState } from "react";

const channels = [
  { id: "telegram", icon: "💬", label: "Telegram", placeholder: "@username" },
  { id: "sms", icon: "📱", label: "SMS", placeholder: "+371 ..." },
  { id: "email", icon: "📧", label: "Email", placeholder: "user@example.com" },
];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function TrackModal({ open, onOpenChange }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set(["email"]));
  const [values, setValues] = useState<Record<string, string>>({
    telegram: "",
    sms: "",
    email: "eva@marketpulse.com",
  });
  const [threshold, setThreshold] = useState(5);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[440px] rounded-modal bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] border-border shadow-card">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold font-display text-foreground">
            How should we notify you?
          </DialogTitle>
        </DialogHeader>

        {/* Channel cards */}
        <div className="flex flex-col gap-2">
          {channels.map((ch) => {
            const active = selected.has(ch.id);
            return (
              <div
                key={ch.id}
                className={`rounded-lg border p-3 transition-colors cursor-pointer ${
                  active
                    ? "border-primary bg-primary/10"
                    : "border-border bg-surface-2"
                }`}
                onClick={() => toggle(ch.id)}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span>{ch.icon}</span>
                  <span className="text-[13px] font-semibold text-foreground">{ch.label}</span>
                  <div
                    className={`ml-auto w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                      active ? "border-primary bg-primary" : "border-muted-foreground"
                    }`}
                  >
                    {active && (
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                        <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                </div>
                {active && (
                  <input
                    type="text"
                    value={values[ch.id]}
                    onChange={(e) => {
                      e.stopPropagation();
                      setValues((prev) => ({ ...prev, [ch.id]: e.target.value }));
                    }}
                    onClick={(e) => e.stopPropagation()}
                    placeholder={ch.placeholder}
                    className="w-full bg-surface text-foreground text-[13px] px-3 py-2 rounded-button border border-border outline-none focus:border-primary transition-colors placeholder:text-muted-foreground"
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Threshold slider */}
        <div className="flex flex-col gap-3 mt-1">
          <div className="flex items-center justify-between">
            <span className="text-[13px] text-foreground">Notify when price changes by:</span>
            <span className="text-[15px] font-bold text-primary">{threshold}%</span>
          </div>
          <Slider
            value={[threshold]}
            onValueChange={([v]) => setThreshold(v)}
            min={1}
            max={30}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between text-[11px] text-muted-foreground">
            <span>1%</span>
            <span>30%</span>
          </div>
        </div>

        {/* Save */}
        <button
          onClick={() => onOpenChange(false)}
          className="w-full mt-2 py-2.5 rounded-button bg-primary text-primary-foreground text-[13px] font-semibold shadow-glow hover:brightness-110 transition-all"
        >
          Save Settings
        </button>
      </DialogContent>
    </Dialog>
  );
}
