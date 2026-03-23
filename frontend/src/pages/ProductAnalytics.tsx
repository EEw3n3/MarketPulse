import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import AiPanel from "@/components/dashboard/AiPanel";
import ProductInfoColumn from "@/components/product/ProductInfoColumn";
import PriceChart from "@/components/product/PriceChart";
import ExportModal from "@/components/product/ExportModal";
import TrackModal from "@/components/product/TrackModal";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import { useIsMobile } from "@/hooks/use-mobile";
import { useAiPanel } from "@/hooks/use-ai-panel";

export default function ProductAnalytics() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [exportOpen, setExportOpen] = useState(false);
  const [trackOpen, setTrackOpen] = useState(false);
  const [period, setPeriod] = useState<string>("1M");
  const { aiPanelOpen, setAiPanelOpen } = useAiPanel(isMobile);

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <div className="hidden md:block">
        <DashboardSidebar onSettingsClick={() => navigate("/settings")} />
      </div>

      <div className="flex-1 flex flex-col md:flex-row min-w-0 overflow-y-auto md:overflow-hidden pb-16 md:pb-0">
        <ProductInfoColumn
          onExport={() => setExportOpen(true)}
          onTrack={() => setTrackOpen(true)}
        />
        <PriceChart period={period} onPeriodChange={setPeriod} />
      </div>

      <AiPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} onOpen={() => setAiPanelOpen(true)} />

      <ExportModal open={exportOpen} onOpenChange={setExportOpen} />
      <TrackModal open={trackOpen} onOpenChange={setTrackOpen} />

      <MobileBottomNav onSettingsClick={() => navigate("/settings")} />
    </div>
  );
}
