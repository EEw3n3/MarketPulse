import { LayoutDashboard, Package, BarChart2, Heart, Settings, Terminal } from "lucide-react";
import logoImg from "@/assets/logo.png";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

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
  const { user } = useAuth();

  const getActiveId = () => {
    if (location.pathname === "/catalog") return "catalog";
    if (location.pathname === "/analytics") return "analytics";
    if (location.pathname === "/favorites") return "favorites";
    if (location.pathname === "/settings") return "settings";
    if (location.pathname === "/admin") return "admin";
    return "dashboard";
  };

  const active = getActiveId();
  const avatarLetter =
    user?.full_name?.[0]?.toUpperCase() ?? user?.email?.[0]?.toUpperCase() ?? "?";

  return (
    <aside className="w-16 h-full flex-col items-center bg-background border-r border-border shrink-0 hidden md:flex">
      {/* Logo */}
      <div className="h-16 flex items-center justify-center w-full border-b border-border">
        <img src={logoImg} alt="MarketPulse" className="h-7 w-auto" />
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col items-center py-5 gap-1">
        {navItems.map((item) => (
          <Tooltip key={item.id} delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => {
                  if (item.id === "settings" && onSettingsClick) onSettingsClick();
                  else navigate(item.path);
                }}
                className={cn(
                  "relative w-10 h-10 flex items-center justify-center rounded-md transition-colors group",
                  active === item.id
                    ? "text-foreground bg-surface"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface/60"
                )}
              >
                {active === item.id && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 -ml-3 w-[2px] h-5 bg-primary rounded-r" />
                )}
                <item.icon size={18} strokeWidth={active === item.id ? 2 : 1.75} />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="bg-surface-2 text-foreground text-[12px] border border-border font-medium">
              {item.label}
            </TooltipContent>
          </Tooltip>
        ))}

        {/* Developer link — admin only */}
        {user?.is_admin && (
          <>
            <div className="w-6 h-px bg-border my-2" />
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  onClick={() => navigate("/admin")}
                  className={cn(
                    "relative w-10 h-10 flex items-center justify-center rounded-md transition-colors",
                    active === "admin"
                      ? "text-amber-400 bg-amber-500/[0.08]"
                      : "text-amber-500/70 hover:text-amber-400 hover:bg-amber-500/[0.05]"
                  )}
                >
                  {active === "admin" && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 -ml-3 w-[2px] h-5 bg-amber-400 rounded-r" />
                  )}
                  <Terminal size={18} strokeWidth={1.75} />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" className="bg-surface-2 text-amber-400 text-[12px] border border-amber-500/30 font-medium">
                Developer
              </TooltipContent>
            </Tooltip>
          </>
        )}
      </nav>

      {/* Avatar */}
      <div className="pb-5 pt-2 w-full flex justify-center border-t border-border">
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <button
              onClick={onSettingsClick}
              className="w-8 h-8 rounded-md bg-surface-2 border border-border text-foreground flex items-center justify-center text-[12px] font-medium hover:border-muted-foreground transition-colors"
            >
              {avatarLetter}
            </button>
          </TooltipTrigger>
          <TooltipContent side="right" className="bg-surface-2 text-foreground text-[12px] border border-border font-medium">
            {user?.full_name ?? user?.email ?? "Account"}
          </TooltipContent>
        </Tooltip>
      </div>
    </aside>
  );
}
