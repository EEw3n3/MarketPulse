import { LayoutDashboard, Package, BarChart2, Heart, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", id: "dashboard" },
  { icon: Package, label: "Catalog", id: "catalog" },
  { icon: BarChart2, label: "Analytics", id: "analytics" },
  { icon: Heart, label: "Favorites", id: "favorites" },
  { icon: Settings, label: "Settings", id: "settings" },
];

interface MobileBottomNavProps {
  onSettingsClick?: () => void;
}

export default function MobileBottomNav({ onSettingsClick }: MobileBottomNavProps) {
  const [active, setActive] = useState("dashboard");

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 h-16 bg-surface border-t border-border flex items-center justify-around px-2 md:hidden">
      {navItems.map((item) => (
        <button
          key={item.id}
          onClick={() => {
            setActive(item.id);
            if (item.id === "settings" && onSettingsClick) onSettingsClick();
          }}
          className={cn(
            "flex flex-col items-center justify-center gap-0.5 w-14 h-14 rounded-xl transition-colors relative",
            active === item.id
              ? "text-primary"
              : "text-muted-foreground"
          )}
        >
          {active === item.id && (
            <span className="absolute inset-1 rounded-xl bg-primary/15 animate-sidebar-icon-scale" />
          )}
          <item.icon size={20} className="relative z-10" />
          <span className="text-[10px] font-medium relative z-10">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
