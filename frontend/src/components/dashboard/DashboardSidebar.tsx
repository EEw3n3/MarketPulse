import { LayoutDashboard, Package, BarChart2, Heart, Settings } from "lucide-react";
import logoImg from "@/assets/logo.png";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useNavigate, useLocation } from "react-router-dom";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", id: "dashboard", path: "/dashboard" },
  { icon: Package, label: "Catalog", id: "catalog", path: "/catalog" },
  { icon: BarChart2, label: "Analytics", id: "analytics", path: "/analytics" },
  { icon: Heart, label: "Favorites", id: "favorites", path: "/favorites" },
  { icon: Settings, label: "Settings", id: "settings", path: "/settings" },
];

interface DashboardSidebarProps {
  onSettingsClick?: () => void;
}

export default function DashboardSidebar({ onSettingsClick }: DashboardSidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const getActiveId = () => {
    if (location.pathname === "/catalog") return "catalog";
    if (location.pathname === "/analytics") return "analytics";
    if (location.pathname === "/favorites") return "favorites";
    if (location.pathname === "/settings") return "settings";
    return "dashboard";
  };

  const active = getActiveId();

  return (
    <aside className="w-16 h-full flex flex-col items-center bg-surface border-r border-border shrink-0 hidden md:flex">
      {/* Logo */}
      <div className="h-16 flex items-center justify-center">
        <img src={logoImg} alt="MarketPulse" className="h-9 w-auto" />
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col items-center justify-center gap-2">
        {navItems.map((item) => (
          <Tooltip key={item.id} delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => {
                  if (item.id === "settings" && onSettingsClick) {
                    onSettingsClick();
                  } else {
                    navigate(item.path);
                  }
                }}
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-colors relative",
                  active === item.id
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
                )}
              >
                {active === item.id && (
                  <span className="absolute inset-0 rounded-full bg-primary/20 animate-sidebar-icon-scale" />
                )}
                <item.icon size={20} className="relative z-10" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="bg-surface-2 text-foreground text-[13px] border-border">
              {item.label}
            </TooltipContent>
          </Tooltip>
        ))}
      </nav>

      {/* Avatar */}
      <div className="pb-4">
        <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-semibold">
          E
        </div>
      </div>
    </aside>
  );
}
