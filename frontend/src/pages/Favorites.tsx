import { useNavigate } from "react-router-dom";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import DashboardTopBar from "@/components/dashboard/DashboardTopBar";
import AiPanel from "@/components/dashboard/AiPanel";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import FavoritesContent from "@/components/favorites/FavoritesContent";
import { useIsMobile } from "@/hooks/use-mobile";
import { useAiPanel } from "@/hooks/use-ai-panel";

export default function Favorites() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { aiPanelOpen, setAiPanelOpen } = useAiPanel(isMobile);

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <div className="hidden md:block">
        <DashboardSidebar onSettingsClick={() => navigate("/settings")} />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <DashboardTopBar onSettingsClick={() => navigate("/settings")} onAiToggle={() => setAiPanelOpen(!aiPanelOpen)} aiPanelOpen={aiPanelOpen} />
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
          <FavoritesContent />
        </main>
      </div>

      <AiPanel open={aiPanelOpen} onClose={() => setAiPanelOpen(false)} onOpen={() => setAiPanelOpen(true)} />
      <MobileBottomNav onSettingsClick={() => navigate("/settings")} />
    </div>
  );
}
