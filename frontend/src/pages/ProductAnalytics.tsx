import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import AiPanel from "@/components/dashboard/AiPanel";
import ProductInfoColumn from "@/components/product/ProductInfoColumn";
import PriceChart from "@/components/product/PriceChart";
import ExportModal from "@/components/product/ExportModal";
import TrackModal from "@/components/product/TrackModal";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import { useIsMobile } from "@/hooks/use-mobile";
import { useAiPanel } from "@/hooks/use-ai-panel";
import { api, ProductCardDetail } from "@/lib/api";
import { RefreshCw, AlertCircle } from "lucide-react";

export default function ProductAnalytics() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isMobile = useIsMobile();
  const [exportOpen, setExportOpen] = useState(false);
  const [trackOpen, setTrackOpen] = useState(false);
  const [period, setPeriod] = useState<string>("1M");
  const { aiPanelOpen, setAiPanelOpen } = useAiPanel(isMobile);

  const [product, setProduct] = useState<ProductCardDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.getProduct(id)
      .then(data => { if (!cancelled) setProduct(data); })
      .catch(err => {
        console.error("Failed to load product:", err);
        if (!cancelled) setError(err?.message ?? "Could not load product.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background gap-4 flex-col">
        <RefreshCw className="animate-spin text-primary" size={32} />
        <p className="text-muted-foreground animate-pulse">Loading product...</p>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="h-screen flex items-center justify-center bg-background gap-3 flex-col px-6 text-center">
        <AlertCircle className="text-destructive" size={28} />
        <p className="text-foreground font-medium">{error ?? "Product not found."}</p>
        <button
          onClick={() => navigate("/dashboard")}
          className="text-[13px] text-primary hover:underline mt-1"
        >
          ← Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <div className="hidden md:block">
        <DashboardSidebar onSettingsClick={() => navigate("/settings")} />
      </div>

      <div className="flex-1 flex flex-col md:flex-row min-w-0 overflow-y-auto md:overflow-hidden pb-16 md:pb-0">
        <ProductInfoColumn
          product={product}
          onExport={() => setExportOpen(true)}
          onTrack={() => setTrackOpen(true)}
        />
        <PriceChart
          period={period}
          onPeriodChange={setPeriod}
          history={product.history}
          storeName={product.store_name}
        />
      </div>

      <AiPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} onOpen={() => setAiPanelOpen(true)} />

      <ExportModal open={exportOpen} onOpenChange={setExportOpen} />
      <TrackModal open={trackOpen} onOpenChange={setTrackOpen} />

      <MobileBottomNav onSettingsClick={() => navigate("/settings")} />
    </div>
  );
}
