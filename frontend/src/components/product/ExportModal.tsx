import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useState } from "react";

const formats = [
  { id: "csv", icon: "📊", label: "CSV" },
  { id: "xlsx", icon: "📋", label: "Excel (.xlsx)" },
  { id: "pdf", icon: "📄", label: "PDF" },
  { id: "json", icon: "🔗", label: "JSON" },
];

const periodOptions = ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "All Time"];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function ExportModal({ open, onOpenChange }: Props) {
  const [format, setFormat] = useState("csv");
  const [period, setPeriod] = useState("1 Month");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[440px] rounded-modal bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] border-border shadow-card">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold font-display text-foreground">
            Export Data
          </DialogTitle>
        </DialogHeader>

        {/* Format */}
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-semibold text-foreground">Format</span>
          <div className="grid grid-cols-2 gap-2">
            {formats.map((f) => (
              <button
                key={f.id}
                onClick={() => setFormat(f.id)}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-[13px] transition-colors border ${
                  format === f.id
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-surface-2 text-muted-foreground hover:text-foreground"
                }`}
              >
                <span>{f.icon}</span>
                <span>{f.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Period */}
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-semibold text-foreground">Period</span>
          <div className="flex flex-wrap gap-1.5">
            {periodOptions.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-full text-[12px] font-semibold transition-colors ${
                  period === p
                    ? "bg-primary text-primary-foreground"
                    : "bg-surface-2 text-muted-foreground hover:text-foreground"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 mt-2">
          <button
            onClick={() => onOpenChange(false)}
            className="text-[13px] text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onOpenChange(false)}
            className="px-5 py-2.5 rounded-button bg-primary text-primary-foreground text-[13px] font-semibold shadow-glow hover:brightness-110 transition-all"
          >
            Download
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
