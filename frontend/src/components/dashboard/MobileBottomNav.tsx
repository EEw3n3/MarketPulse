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
    <nav className="fixed bottom-0 left-0 right-0 z-40 h-14 bg-background border-t border-border flex items-center justify-around px-2 md:hidden">
      {navItems.map((item) => (
        <button
          key={item.id}
          onClick={() => {
            setActive(item.id);
            if (item.id === "settings" && onSettingsClick) onSettingsClick();
          }}
          className={cn(
            "relative flex flex-col items-center justify-center gap-0.5 w-14 h-full transition-colors",
            active === item.id ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {active === item.id && (
            <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] bg-primary rounded-b" />
          )}
          <item.icon size={18} strokeWidth={active === item.id ? 2 : 1.75} />
          <span className="text-[10px] font-medium">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
