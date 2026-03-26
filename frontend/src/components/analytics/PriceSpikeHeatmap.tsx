import { useState } from "react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { TrendingDown, AlertTriangle } from "lucide-react";

const brands = ["Dior", "Chanel", "YSL", "Tom Ford", "Armani", "Versace"];
const stores = ["Douglas", "Notino", "Sephora", "Parfumdreams", "Flaconi"];

// Mock variance data: 0 is median, negative is dumping
const matrix: Record<string, Record<string, number>> = {
  "Dior": { "Douglas": 2, "Notino": -15, "Sephora": 0, "Parfumdreams": -5, "Flaconi": -2 },
  "Chanel": { "Douglas": -12, "Notino": 0, "Sephora": 5, "Parfumdreams": -2, "Flaconi": -8 },
  "YSL": { "Douglas": 1, "Notino": -18, "Sephora": -1, "Parfumdreams": -4, "Flaconi": 0 },
  "Tom Ford": { "Douglas": 0, "Notino": -5, "Sephora": -12, "Parfumdreams": 0, "Flaconi": 3 },
  "Armani": { "Douglas": -8, "Notino": 4, "Sephora": -2, "Parfumdreams": -10, "Flaconi": 1 },
  "Versace": { "Douglas": 5, "Notino": -22, "Sephora": 2, "Parfumdreams": -14, "Flaconi": -5 },
};

const getCellColor = (val: number) => {
  if (val > 0) return "bg-success/10 text-[hsl(var(--success))] border-success/20";
  if (val === 0) return "bg-surface-2/50 text-muted-foreground border-transparent";
  if (val > -5) return "bg-orange-500/15 text-orange-400 border-orange-500/30";
  if (val > -15) return "bg-destructive/30 text-red-400 border-destructive/50";
  return "bg-destructive/80 text-white border-destructive shadow-[0_0_15px_rgba(239,68,68,0.4)]"; // severe dumping
};

const getDrilldownData = (brand: string, store: string) => {
  // Deterministic mock generation based on brand/store name lengths
  const seed = brand.length + store.length;
  return [
    { name: `${brand} Flagship EDP 100ml`, price: 85.00, regularPrice: 115.00, drop: -15 - (seed % 15) },
    { name: `${brand} Intense Parfum 50ml`, price: 110.00, regularPrice: 130.00, drop: -5 - (seed % 10) },
    { name: `${brand} Fresh EDT 75ml`, price: 65.00, regularPrice: 70.00, drop: -2 - (seed % 5) }
  ].sort((a, b) => a.drop - b.drop); // Worst violations first
};

export default function PriceSpikeHeatmap() {
  const [selectedCell, setSelectedCell] = useState<{ brand: string; store: string } | null>(null);

  return (
    <div className="w-full overflow-x-auto pb-2 scrollbar-hide">
      <div className="min-w-[500px]">
        {/* Header row */}
        <div className="grid grid-cols-[100px_repeat(5,1fr)] gap-2 mb-3">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium px-2 py-1">Brand</div>
          {stores.map(store => (
            <div key={store} className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium px-2 py-1 text-center truncate">
              {store}
            </div>
          ))}
        </div>
        
        {/* Matrix */}
        <div className="flex flex-col gap-2">
          <TooltipProvider delayDuration={100}>
            {brands.map(brand => (
              <div key={brand} className="grid grid-cols-[100px_repeat(5,1fr)] gap-2">
                <div className="flex items-center text-[12px] font-medium text-foreground px-2">
                  {brand}
                </div>
                {stores.map(store => {
                  const val = matrix[brand]?.[store] ?? 0;
                  const colorClass = getCellColor(val);
                  
                  return (
                    <Tooltip key={`${brand}-${store}`}>
                      <TooltipTrigger asChild>
                        <div 
                          onClick={() => setSelectedCell({ brand, store })}
                          className={cn(
                          "h-10 rounded-[var(--radius-button)] border flex items-center justify-center text-[12px] font-display tabular-nums tracking-tight font-medium cursor-pointer transition-all duration-300 hover:scale-[1.05] hover:shadow-glow hover:z-10 relative",
                          colorClass
                        )}>
                          {val > 0 ? "+" : ""}{val}%
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="bg-surface/95 backdrop-blur-xl border border-border shadow-[0_12px_32px_rgba(0,0,0,0.6)] p-3 rounded-[var(--radius-card)] z-50">
                        <p className="text-[13px] font-medium text-foreground mb-1">{brand} at {store}</p>
                        <p className="text-[12px] text-muted-foreground">Variance from market median: <span className={cn("font-bold font-display tabular-nums tracking-tight ml-1", val < -10 ? "text-destructive" : val < 0 ? "text-orange-400" : "text-[hsl(var(--success))]")}>{val > 0 ? "+" : ""}{val}%</span></p>
                        {val <= -15 && <p className="text-[10px] text-destructive mt-1.5 uppercase tracking-widest font-bold flex items-center gap-1">⚠️ Severe MAP Violation</p>}
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            ))}
          </TooltipProvider>
        </div>
      </div>

      <Sheet open={!!selectedCell} onOpenChange={(open) => !open && setSelectedCell(null)}>
        <SheetContent className="w-[340px] sm:w-[450px] border-l border-border bg-surface/95 backdrop-blur-xl p-0 flex flex-col">
          <SheetHeader className="p-6 border-b border-border bg-background/50 flex flex-col gap-1 items-start">
            <div className="flex items-center gap-2">
              <AlertTriangle className="text-destructive h-5 w-5" />
              <SheetTitle className="text-lg font-display tracking-tight text-foreground m-0">
                MAP Violations Drill-down
              </SheetTitle>
            </div>
            <p className="text-[13px] text-muted-foreground w-full">
              Specific anomalies triggering the <span className="font-bold text-foreground">{selectedCell?.brand}</span> × <span className="font-bold text-foreground">{selectedCell?.store}</span> spike.
            </p>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
            {selectedCell && (
              <div className="space-y-3">
                {getDrilldownData(selectedCell.brand, selectedCell.store).map((item, idx) => (
                  <div key={idx} className="p-4 rounded-[var(--radius-card)] border border-border bg-surface-2/30 hover:bg-surface-2 hover:-translate-y-0.5 hover:shadow-card transition-all flex items-center justify-between group cursor-default">
                    <div>
                      <h4 className="text-[13px] font-medium text-foreground group-hover:text-primary transition-colors pr-4">{item.name}</h4>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className="text-[14px] font-bold font-display tabular-nums tracking-tight text-foreground">€{item.price.toFixed(2)}</span>
                        <span className="text-[11px] text-muted-foreground line-through tabular-nums">€{item.regularPrice.toFixed(2)}</span>
                      </div>
                    </div>
                    <Badge variant="outline" className={cn(
                      "text-[11px] font-medium tabular-nums tracking-tight border-0 px-2 py-0.5 flex shrink-0",
                      item.drop <= -15 ? "bg-destructive/15 text-destructive" : item.drop < 0 ? "bg-orange-500/15 text-orange-400" : "bg-success/15 text-[hsl(var(--success))]"
                    )}>
                      {item.drop < 0 && <TrendingDown size={11} className="mr-1 mt-[1px]" />}
                      {item.drop > 0 ? "+" : ""}{item.drop}%
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
