import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { BarChart3, Heart, LayoutGrid, LogOut, Sun, User } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useFavorites } from "@/contexts/FavoritesContext";
import { useT } from "@/i18n";
import { hasPro } from "@/lib/plan";
import ChatPanel from "./ChatPanel";
import LangSwitch from "./LangSwitch";
import SearchBox from "./SearchBox";

function AvatarMenu() {
  const t = useT();
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (!user) return null;
  const name = user.full_name?.trim() || user.email.split("@")[0];
  const pro = hasPro(user);
  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button className="ava" type="button" aria-haspopup="menu" aria-expanded={open} aria-label={t.shell.account} onClick={() => setOpen((o) => !o)}>
        {name[0]?.toUpperCase()}
      </button>
      {open && (
        <div className="menu fade" role="menu">
          <div className="who">
            <b>{name}</b>
            <small>{user.email}</small>
            <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
              <span className={`tag ${pro ? "tag-pro" : ""}`}>{pro ? t.shell.planPro : t.shell.planFree}</span>
              {user.is_admin && <span className="tag" style={{ background: "var(--f-douglas)", color: "var(--ink)" }}>{t.shell.admin}</span>}
            </div>
          </div>
          <Link role="menuitem" to="/profile" onClick={() => setOpen(false)}>
            {t.shell.nav.profile}
            <User size={16} />
          </Link>
          {!pro && (
            <Link role="menuitem" to="/profile#plan" onClick={() => setOpen(false)}>
              {t.shell.getPro}
              <span className="tag tag-pro">{t.common.pro}</span>
            </Link>
          )}
          <div style={{ padding: "6px 12px" }}>
            <LangSwitch />
          </div>
          <button
            role="menuitem"
            type="button"
            onClick={() => {
              setOpen(false);
              logout();
              nav("/");
            }}
          >
            {t.shell.signOut}
            <LogOut size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

/** Top bar, mobile bottom bar and the AI chat around every signed-in page. */
export default function AppShell({ children, search = true }: { children: ReactNode; search?: boolean }) {
  const t = useT();
  const { user } = useAuth();
  const { ids } = useFavorites();
  const { pathname } = useLocation();
  const pro = hasPro(user);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  const tabs = [
    { to: "/today", label: t.shell.nav.today, icon: <Sun /> },
    { to: "/catalog", label: t.shell.nav.catalog, icon: <LayoutGrid /> },
    {
      to: "/favorites",
      label: t.shell.nav.favorites,
      icon: <Heart />,
      extra: ids.size > 0 ? <span className="count num">{ids.size}</span> : null,
    },
    {
      to: "/analytics",
      label: t.shell.nav.analytics,
      icon: <BarChart3 />,
      extra: <span className="pro">{t.common.pro}</span>,
    },
  ];

  return (
    <>
      <a className="sr" href="#main" onFocus={(e) => e.currentTarget.classList.remove("sr")} onBlur={(e) => e.currentTarget.classList.add("sr")}>
        {t.shell.skip}
      </a>
      <header className="top wrap">
        <Link className="logo" to="/today">
          MarketPulse
        </Link>
        <nav className="tabs" aria-label={t.shell.mainNav}>
          {tabs.map((tab) => (
            <NavLink key={tab.to} to={tab.to} aria-current={pathname.startsWith(tab.to) ? "page" : undefined}>
              {tab.label}
              {tab.extra}
            </NavLink>
          ))}
          {user?.is_admin && (
            <NavLink to="/admin" aria-current={pathname.startsWith("/admin") ? "page" : undefined}>
              {t.shell.nav.admin}
            </NavLink>
          )}
        </nav>
        {search ? <SearchBox /> : <span style={{ marginLeft: "auto" }} />}
        <LangSwitch />
        <AvatarMenu />
      </header>
      <main id="main" className="wrap app-main">
        {children}
      </main>
      <nav className="bnav" aria-label={t.shell.mainNav}>
        {tabs.map((tab) => (
          <NavLink key={tab.to} to={tab.to} aria-current={pathname.startsWith(tab.to) ? "page" : undefined}>
            {tab.icon}
            {tab.label}
            {tab.to === "/analytics" && !pro && <span className="pro">{t.common.pro}</span>}
          </NavLink>
        ))}
        <NavLink to="/profile" aria-current={pathname.startsWith("/profile") ? "page" : undefined}>
          <User />
          {t.shell.nav.profile}
        </NavLink>
      </nav>
      <ChatPanel key={user?.id ?? "anon"} />
    </>
  );
}
