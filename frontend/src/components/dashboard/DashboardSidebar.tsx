import { LayoutDashboard, Package, BarChart2, Heart, Settings } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useState } from "react";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", id: "dashboard" },
  { icon: Package, label: "Catalog", id: "catalog" },
  { icon: BarChart2, label: "Analytics", id: "analytics" },
  { icon: Heart, label: "Favorites", id: "favorites" },
  { icon: Settings, label: "Settings", id: "settings" },
];

interface DashboardSidebarProps {
  onSettingsClick?: () => void;
}

export default function DashboardSidebar({ onSettingsClick }: DashboardSidebarProps) {
  const [active, setActive] = useState("dashboard");

  return (
    <aside className="w-16 h-full flex flex-col items-center bg-surface border-r border-border shrink-0 hidden md:flex">
      {/* Logo */}
      <div className="h-16 flex items-center justify-center">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <polygon
            points="16,1 29,8.5 29,23.5 16,31 3,23.5 3,8.5"
            fill="hsl(263 70% 58%)"
            opacity="0.15"
            stroke="hsl(263 70% 58%)"
            strokeWidth="1.5"
          />
          <text
            x="16"
            y="21"
            textAnchor="middle"
            fill="hsl(263 70% 58%)"
            fontSize="14"
            fontWeight="700"
            fontFamily="Outfit, sans-serif"
          >
            M
          </text>
        </svg>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col items-center justify-center gap-2">
        {navItems.map((item) => (
          <Tooltip key={item.id} delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => {
                  setActive(item.id);
                  if (item.id === "settings" && onSettingsClick) onSettingsClick();
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
