import { useNavigate } from "react-router-dom";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import DashboardTopBar from "@/components/dashboard/DashboardTopBar";
import AiPanel from "@/components/dashboard/AiPanel";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import AnalyticsContent from "@/components/analytics/AnalyticsContent";
import { useIsMobile } from "@/hooks/use-mobile";
import { useAiPanel } from "@/hooks/use-ai-panel";

export default function Analytics() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { aiPanelOpen, setAiPanelOpen } = useAiPanel(isMobile);

  const openSettings = () => navigate("/settings");

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <div className="hidden md:block">
        <DashboardSidebar onSettingsClick={openSettings} />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <DashboardTopBar
          onSettingsClick={openSettings}
          onAiToggle={() => setAiPanelOpen(!aiPanelOpen)}
          aiPanelOpen={aiPanelOpen}
        />
        <AnalyticsContent />
      </div>

      <AiPanel
        open={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
        onOpen={() => setAiPanelOpen(true)}
      />

      <MobileBottomNav onSettingsClick={openSettings} />
    </div>
  );
}
