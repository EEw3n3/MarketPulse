import { ArrowLeft, Upload, Bell } from "lucide-react";
import { useNavigate } from "react-router-dom";

const stores = [
  { name: "Douglas.lv", price: 125.0, best: true, dot: "bg-blue-500" },
  { name: "Notino.lv", price: 129.99, best: false, dot: "bg-success" },
  { name: "1a.lv", price: 134.95, best: false, dot: "bg-foreground" },
];

interface Props {
  onExport: () => void;
  onTrack: () => void;
}

export default function ProductInfoColumn({ onExport, onTrack }: Props) {
  const navigate = useNavigate();

  return (
    <div className="w-full md:w-[380px] md:h-full flex flex-col md:overflow-y-auto border-b md:border-b-0 md:border-r border-border bg-surface shrink-0 scrollbar-hide">
      <div className="p-6 flex flex-col gap-5">
        {/* Back */}
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-primary transition-colors w-fit"
        >
          <ArrowLeft size={14} />
          All Products
        </button>

        {/* Product image */}
        <div className="w-[320px] h-[320px] mx-auto rounded-card border border-border bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] shadow-[0_0_40px_rgba(124,58,237,0.15)] flex items-center justify-center transition-transform duration-250 ease-brand hover:scale-[1.03] cursor-pointer">
          <span className="text-muted-foreground text-4xl opacity-30 select-none">📦</span>
        </div>

        {/* Brand + Name */}
        <div className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-widest text-muted-foreground">DIOR</span>
          <h1 className="text-[32px] font-bold font-display leading-tight text-foreground">
            Sauvage Eau de Parfum
          </h1>
        </div>

        {/* Volume chips */}
        <div className="flex gap-2">
          <span className="px-3 py-1 rounded-full bg-surface-2 text-[12px] text-muted-foreground">100 ml</span>
          <span className="px-3 py-1 rounded-full bg-surface-2 text-[12px] text-muted-foreground">EDP</span>
        </div>

        {/* Current price */}
        <div className="flex items-end gap-3">
          <span className="text-[48px] font-bold font-display leading-none text-foreground price-display">
            125.00 €
          </span>
        </div>

        {/* Previous price + change */}
        <div className="flex items-center gap-2 -mt-2">
          <span className="text-[13px] text-muted-foreground line-through">135.00 €</span>
          <span className="px-2 py-0.5 rounded-full bg-success/20 text-success text-[12px] font-semibold">
            ↓ −7.4%
          </span>
        </div>

        {/* Cross-site comparison */}
        <div className="flex flex-col gap-1.5 mt-2">
          <span className="text-[13px] font-semibold text-foreground mb-1">Price Comparison</span>
          {stores.map((s) => (
            <div
              key={s.name}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                s.best ? "bg-success/10 border border-success/20" : "bg-surface-2"
              }`}
            >
              <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${s.dot}`} />
              <span className="text-[13px] text-foreground flex-1">{s.name}</span>
              <span className={`text-[13px] font-semibold price-display ${s.best ? "text-success" : "text-foreground"}`}>
                {s.price.toFixed(2)} €
              </span>
              {s.best && (
                <span className="text-[11px] text-success font-semibold">Best ✓</span>
              )}
            </div>
          ))}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-2 mt-3">
          <button
            onClick={onExport}
            className="w-full h-11 rounded-button border border-primary text-primary text-[13px] font-semibold flex items-center justify-center gap-2 hover:bg-primary/10 transition-colors"
          >
            <Upload size={15} />
            Export
          </button>
          <button
            onClick={onTrack}
            className="w-full h-11 rounded-button bg-primary text-primary-foreground text-[13px] font-semibold flex items-center justify-center gap-2 shadow-glow hover:brightness-110 transition-all"
          >
            <Bell size={15} />
            Track Price
          </button>
        </div>
      </div>
    </div>
  );
}
