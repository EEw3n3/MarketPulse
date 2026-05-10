import { Search, Bell, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

interface DashboardTopBarProps {
  onSettingsClick?: () => void;
  onAiToggle?: () => void;
  aiPanelOpen?: boolean;
}

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/catalog": "Catalog",
  "/analytics": "Analytics",
  "/favorites": "Favorites",
  "/settings": "Settings",
  "/admin": "Admin Panel",
};

function getPageTitle(pathname: string): string {
  if (pathname.startsWith("/product/")) return "Product";
  return PAGE_TITLES[pathname] ?? "Dashboard";
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 5) return "Late night";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardTopBar({ onSettingsClick }: DashboardTopBarProps) {
  const { user } = useAuth();
  const location = useLocation();
  const pageTitle = getPageTitle(location.pathname);
  const [isDark, setIsDark] = useState(true);

  const [searchParams, setSearchParams] = useSearchParams();
  const urlSearch = searchParams.get("search") ?? "";
  const [searchInput, setSearchInput] = useState(urlSearch);

  // Sync input when navigating between routes (URL changes externally)
  useEffect(() => {
    setSearchInput(urlSearch);
  }, [urlSearch]);

  // Debounced commit: write the search input back to URL after 300ms idle.
  useEffect(() => {
    const t = setTimeout(() => {
      const trimmed = searchInput.trim();
      if (trimmed === urlSearch) return;
      const next = new URLSearchParams(searchParams);
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      setSearchParams(next, { replace: true });
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleTheme = () => {
    setIsDark(!isDark);
    document.documentElement.classList.toggle("light");
  };

  const firstName = user?.full_name?.split(" ")[0] ?? user?.email?.split("@")[0] ?? "there";
  // Search lives only on Dashboard — Catalog has its own dedicated search,
  // and other pages have nothing to search against.
  const showSearch = location.pathname === "/dashboard";

  return (
    <header className="h-14 flex items-center px-5 lg:px-7 bg-background border-b border-border shrink-0">
      {/* Left — page title / greeting */}
      <div className="flex items-baseline gap-3 min-w-0">
        <h1 className="font-['Inter'] font-semibold text-foreground text-[15px] tracking-[-0.005em] whitespace-nowrap">
          {pageTitle}
        </h1>
        <span className="hidden md:inline-flex items-center gap-1.5 text-[12px] text-muted-foreground truncate">
          <span className="w-px h-3 bg-border" />
          {getGreeting()}, {firstName}
        </span>
      </div>

      {/* Center — Search (Dashboard only) */}
      {showSearch ? (
        <div className="flex-1 flex justify-center px-4">
          <div className="relative w-full max-w-[480px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              data-tutorial="search"
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search products, brands, retailers…"
              className="w-full h-9 pl-9 pr-16 rounded-md bg-surface border border-border text-[13px] text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
            />
            <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[10px] font-medium text-muted-foreground bg-background border border-border px-1.5 py-0.5 rounded">
              ⌘K
            </kbd>
          </div>
        </div>
      ) : (
        <div className="flex-1" />
      )}

      {/* Right */}
      <div className="flex items-center gap-1.5">
        {/* Bell */}
        <button className="relative w-9 h-9 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors">
          <Bell size={16} strokeWidth={1.75} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-primary ring-2 ring-background" />
        </button>

        {/* Theme toggle — simple ghost button */}
        <button
          onClick={toggleTheme}
          className="w-9 h-9 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors"
          aria-label="Toggle theme"
        >
          {isDark ? <Moon size={15} strokeWidth={1.75} /> : <Sun size={15} strokeWidth={1.75} />}
        </button>

        <span className="w-px h-5 bg-border mx-2" />

        {/* Account */}
        <button
          data-tutorial="account"
          onClick={onSettingsClick}
          className="flex items-center gap-2 pl-1.5 pr-3 py-1.5 rounded-md hover:bg-surface transition-colors"
        >
          <div className="w-7 h-7 rounded-md bg-surface-2 border border-border text-foreground flex items-center justify-center text-[11px] font-medium">
            {(user?.full_name?.[0] ?? user?.email?.[0] ?? "?").toUpperCase()}
          </div>
          <span className="hidden lg:inline text-[12px] text-foreground font-medium max-w-[140px] truncate">
            {user?.full_name ?? user?.email ?? "Account"}
          </span>
        </button>
      </div>
    </header>
  );
}
