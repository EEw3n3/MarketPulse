import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import AiPanel from "@/components/dashboard/AiPanel";
import ProductInfoColumn from "@/components/product/ProductInfoColumn";
import PriceChart from "@/components/product/PriceChart";
import ExportModal from "@/components/product/ExportModal";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import { useIsMobile } from "@/hooks/use-mobile";
import { useAiPanel } from "@/hooks/use-ai-panel";
import { api, ProductCardDetail } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui/state-views";

export default function ProductAnalytics() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isMobile = useIsMobile();
  const [exportOpen, setExportOpen] = useState(false);
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
    return <LoadingState label="Loading product" fullscreen />;
  }

  if (error || !product) {
    return (
      <ErrorState
        message={error ?? "Product not found."}
        onRetry={() => navigate("/dashboard")}
        retryLabel="Back to dashboard"
        fullscreen
      />
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
        />
        <PriceChart
          period={period}
          onPeriodChange={setPeriod}
          history={product.history}
          storeName={product.store_name}
        />
      </div>

      <AiPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} onOpen={() => setAiPanelOpen(true)} />

      <ExportModal open={exportOpen} onOpenChange={setExportOpen} scope="product" product={product} />

      <MobileBottomNav onSettingsClick={() => navigate("/settings")} />
    </div>
  );
}
