import { Search, Bell, Moon, Sun, ChevronDown } from "lucide-react";
import { useState } from "react";

interface DashboardTopBarProps {
  onSettingsClick?: () => void;
  onAiToggle?: () => void;
  aiPanelOpen?: boolean;
}

export default function DashboardTopBar({ onSettingsClick, onAiToggle, aiPanelOpen }: DashboardTopBarProps) {
  const [isDark, setIsDark] = useState(true);
  const [searchFocused, setSearchFocused] = useState(false);

  const toggleTheme = () => {
    setIsDark(!isDark);
    document.documentElement.classList.toggle("light");
  };

  return (
    <header className="h-16 flex items-center px-6 bg-surface border-b border-border shrink-0">
      {/* Left */}
      <h2 className="text-lg text-foreground font-medium whitespace-nowrap">
        Good evening, Ervin 👋
      </h2>

      {/* Center */}
      <div className="flex-1 flex justify-center px-4">
        <div
          className={`relative w-full max-w-[520px] rounded-card transition-all ${
            searchFocused ? "ring-2 ring-primary shadow-glow" : ""
          }`}
        >
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            data-tutorial="search"
            type="text"
            placeholder="Search perfume, brand..."
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            className="w-full h-10 pl-9 pr-16 rounded-card bg-[rgba(255,255,255,0.04)] backdrop-blur-[16px] border border-border text-sm text-foreground placeholder:text-muted-foreground outline-none"
          />
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground bg-surface-2 px-1.5 py-0.5 rounded">
            Ctrl+K
          </kbd>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {/* Bell */}
        <button className="relative w-10 h-10 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors">
          <Bell size={20} />
          <span className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground flex items-center justify-center animate-badge-bounce">
            3
          </span>
        </button>

        {/* Theme toggle */}
        <div className="flex items-center bg-surface-2 rounded-full p-0.5 gap-0.5">
          <button
            onClick={() => { if (!isDark) toggleTheme(); }}
            className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              isDark ? "bg-primary text-primary-foreground" : "text-muted-foreground"
            }`}
          >
            <Moon size={14} />
          </button>
          <button
            onClick={() => { if (isDark) toggleTheme(); }}
            className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              !isDark ? "bg-primary text-primary-foreground" : "text-muted-foreground"
            }`}
          >
            <Sun size={14} />
          </button>
        </div>

        {/* Avatar dropdown */}
        <button data-tutorial="account" className="flex items-center gap-1.5" onClick={onSettingsClick}>
          <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-semibold">
            E
          </div>
          <ChevronDown size={14} className="text-muted-foreground" />
        </button>
      </div>
    </header>
  );
}
