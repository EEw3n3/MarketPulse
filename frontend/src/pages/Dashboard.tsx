import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import DashboardTopBar from "@/components/dashboard/DashboardTopBar";
import DashboardFilterBar from "@/components/dashboard/DashboardFilterBar";
import AiPanel from "@/components/dashboard/AiPanel";
import ProductFeed from "@/components/dashboard/ProductFeed";
import GuidedTutorial from "@/components/dashboard/GuidedTutorial";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import { useIsMobile } from "@/hooks/use-mobile";
import { useAiPanel } from "@/hooks/use-ai-panel";

export default function Dashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [showTutorial, setShowTutorial] = useState(
    !!(location.state as any)?.showTutorial
  );
  const { aiPanelOpen, setAiPanelOpen } = useAiPanel(isMobile);

  const openSettings = () => navigate("/settings");

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      {showTutorial && (
        <GuidedTutorial 
          onComplete={() => {
            setShowTutorial(false);
            setAiPanelOpen(false);
          }} 
          onStepChange={(stepIdx) => {
            setAiPanelOpen(stepIdx === 4);
          }}
        />
      )}
      
      {/* Sidebar: hidden on mobile */}
      <div className="hidden md:block">
        <DashboardSidebar onSettingsClick={openSettings} />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <DashboardTopBar onSettingsClick={openSettings} onAiToggle={() => setAiPanelOpen(!aiPanelOpen)} aiPanelOpen={aiPanelOpen} />
        <DashboardFilterBar />
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0" data-tutorial="feed">
          <ProductFeed />
        </main>
      </div>

      <AiPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} onOpen={() => setAiPanelOpen(true)} />

      {/* Mobile bottom nav */}
      <MobileBottomNav onSettingsClick={openSettings} />
    </div>
  );
}
