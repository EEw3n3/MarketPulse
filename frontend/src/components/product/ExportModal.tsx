import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ProductCardDetail } from "@/lib/api";
import {
  PERIOD_TO_CODE,
  periodToDays,
  exportCsv,
  exportJson,
  exportProductBackend,
  exportCatalogBackend,
  safeFilename,
  type ExportFormat,
} from "@/lib/exporters";

const formats: { id: ExportFormat; icon: string; label: string }[] = [
  { id: "csv", icon: "📊", label: "CSV" },
  { id: "xlsx", icon: "📋", label: "Excel (.xlsx)" },
  { id: "pdf", icon: "📄", label: "PDF" },
  { id: "json", icon: "🔗", label: "JSON" },
];

const periodOptions = ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "All Time"];

type Scope = "product" | "catalog";

interface CatalogFilters {
  search?: string;
  brands?: string[];
  stores?: string[];
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scope: Scope;
  /** Required for scope='product'. */
  product?: ProductCardDetail;
  /** Required for scope='catalog'. */
  filters?: CatalogFilters;
}

export default function ExportModal({ open, onOpenChange, scope, product, filters }: Props) {
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [period, setPeriod] = useState("1 Month");
  const [downloading, setDownloading] = useState(false);

  const periodCode = PERIOD_TO_CODE[period] ?? "1m";

  async function handleDownload() {
    setDownloading(true);
    try {
      if (scope === "product") {
        if (!product) throw new Error("No product to export");
        const baseName = safeFilename(`${product.brand ?? ""} ${product.title}`.trim());
        await downloadProduct(product, format, periodCode, baseName);
      } else {
        const date = new Date().toISOString().slice(0, 10);
        const baseName = `marketpulse_catalog_${date}`;
        await downloadCatalog(filters ?? {}, format, baseName);
      }
      toast.success(`${format.toUpperCase()} downloaded`);
      onOpenChange(false);
    } catch (err) {
      console.error("Export failed", err);
      toast.error(err instanceof Error ? err.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[440px] rounded-modal bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] border-border shadow-card">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold font-display text-foreground">
            Export {scope === "product" ? "Product" : "Catalog"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-semibold text-foreground">Format</span>
          <div className="grid grid-cols-2 gap-2">
            {formats.map((f) => (
              <button
                key={f.id}
                onClick={() => setFormat(f.id)}
                disabled={downloading}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-[13px] transition-colors border ${
                  format === f.id
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-surface-2 text-muted-foreground hover:text-foreground"
                } disabled:opacity-50`}
              >
                <span>{f.icon}</span>
                <span>{f.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Period — only meaningful for single-product export (filters PriceHistory).
            Catalog export doesn't use period (catalog is a snapshot, not a series). */}
        {scope === "product" && (
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-semibold text-foreground">Period</span>
            <div className="flex flex-wrap gap-1.5">
              {periodOptions.map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  disabled={downloading}
                  className={`px-3 py-1.5 rounded-full text-[12px] font-semibold transition-colors ${
                    period === p
                      ? "bg-primary text-primary-foreground"
                      : "bg-surface-2 text-muted-foreground hover:text-foreground"
                  } disabled:opacity-50`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 mt-2">
          <button
            onClick={() => onOpenChange(false)}
            disabled={downloading}
            className="text-[13px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-button bg-primary text-primary-foreground text-[13px] font-semibold shadow-glow hover:brightness-110 transition-all disabled:opacity-60"
          >
            {downloading && <Loader2 size={14} className="animate-spin" />}
            {downloading ? "Generating…" : "Download"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Dispatch helpers ─────────────────────────────────────────────────────────

async function downloadProduct(
  product: ProductCardDetail,
  format: ExportFormat,
  periodCode: string,
  baseName: string,
): Promise<void> {
  if (format === "csv") {
    const days = periodToDays(periodCode);
    const cutoff = days ? Date.now() - days * 86400_000 : 0;
    const rows = (product.history ?? [])
      .filter(h => !cutoff || new Date(h.parsed_at).getTime() >= cutoff)
      .sort((a, b) => new Date(a.parsed_at).getTime() - new Date(b.parsed_at).getTime())
      .map(h => ({
        date: h.parsed_at,
        price: Number(h.price),
        in_stock: h.in_stock ? "Yes" : "No",
        change_type: h.change_type ?? "",
      }));
    exportCsv(rows, `${baseName}.csv`, ["date", "price", "in_stock", "change_type"]);
    return;
  }
  if (format === "json") {
    exportJson(product, `${baseName}.json`);
    return;
  }
  await exportProductBackend(
    { productId: product.id, format, period: periodCode },
    baseName,
  );
}

async function downloadCatalog(
  filters: CatalogFilters,
  format: ExportFormat,
  baseName: string,
): Promise<void> {
  if (format === "csv" || format === "json") {
    // Fetch a wide page from /products/catalog with the same filters
    const { api } = await import("@/lib/api");
    const q = new URLSearchParams();
    if (filters.search) q.set("search", filters.search);
    (filters.brands ?? []).forEach(b => q.append("brands", b));
    (filters.stores ?? []).forEach(s => q.append("stores", s));
    q.set("limit", "2000");
    const rows = await api.getCatalog(q.toString());
    if (format === "csv") {
      const cleaned = rows.map(r => ({
        brand: r.brand,
        title: r.name,
        volume: r.volume,
        type: r.type,
        store: r.store,
        price: r.price,
        previous_price: r.previousPrice,
        change_percent: r.changePercent,
        change_direction: r.changeDirection,
        in_stock: r.in_stock ? "Yes" : "No",
        last_updated: r.lastUpdated,
      }));
      exportCsv(cleaned, `${baseName}.csv`);
    } else {
      exportJson(rows, `${baseName}.json`);
    }
    return;
  }
  await exportCatalogBackend({ format, ...filters }, baseName);
}
