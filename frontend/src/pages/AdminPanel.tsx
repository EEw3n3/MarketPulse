import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Database,
  RefreshCw,
  Users,
  ScrollText,
  PlayCircle,
  Sparkles,
  CheckCircle,
  XCircle,
  ChevronRight,
  Loader,
} from "lucide-react";
import { cn } from "@/lib/utils";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import MobileBottomNav from "@/components/dashboard/MobileBottomNav";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  api,
  AdminHealthResponse,
  AdminDataQuality,
  AdminUserRead,
  AdminLogsResponse,
  AdminScrapingRule,
} from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui/state-views";
import { toast } from "sonner";

type Tab = "health" | "scraping" | "quality" | "users";

const TABS: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: "health", label: "Health", icon: Activity },
  { id: "scraping", label: "Scraping", icon: PlayCircle },
  { id: "quality", label: "Data Quality", icon: Database },
  { id: "users", label: "Users", icon: Users },
];

// ── Health Tab ─────────────────────────────────────────────────────────────

function HealthTab() {
  const [data, setData] = useState<AdminHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.admin.health()
      .then(setData)
      .catch((e) => setError(e?.message ?? "Failed to load health"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingState label="Loading health" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-5">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-md border border-border overflow-hidden">
        {[
          { label: "Total products", value: data.total_products.toLocaleString() },
          { label: "Registered users", value: data.total_users },
          { label: "Sites tracked", value: data.sites.length },
          { label: "DB latency", value: `${data.db_latency_ms} ms` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface/40 px-5 py-4 flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span>
            <span className="font-mono font-semibold tabular-nums text-[22px] text-foreground">{value}</span>
          </div>
        ))}
      </div>

      {/* Sites table */}
      <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
        <div className="grid grid-cols-[1fr_80px_80px_90px_90px_80px] gap-3 px-5 py-3 border-b border-border bg-surface/60">
          {["Domain", "Products", "Health", "Success", "Failure", "Last scrape"].map((h) => (
            <span key={h} className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{h}</span>
          ))}
        </div>
        <div className="divide-y divide-border">
          {data.sites.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">No scraping rules found.</p>
            </div>
          ) : data.sites.map((s) => (
            <div key={s.domain} className="grid grid-cols-[1fr_80px_80px_90px_90px_80px] gap-3 px-5 py-3 items-center">
              <div className="min-w-0">
                <p className="font-mono text-[12px] text-foreground">{s.domain}</p>
                <p className="font-mono text-[10px] text-muted-foreground truncate">{s.site_name}</p>
              </div>
              <span className="font-mono tabular-nums text-[12px] text-foreground">{s.product_count}</span>
              <div className="flex items-center gap-1.5">
                <div className="w-full h-1 bg-surface-2 rounded-full overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", s.health_score > 0.7 ? "bg-[hsl(var(--success))]" : s.health_score > 0.4 ? "bg-amber-500" : "bg-destructive")}
                    style={{ width: `${s.health_score * 100}%` }}
                  />
                </div>
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground shrink-0">
                  {(s.health_score * 100).toFixed(0)}%
                </span>
              </div>
              <span className="font-mono tabular-nums text-[12px] text-[hsl(var(--success))]">{s.success_count}</span>
              <span className="font-mono tabular-nums text-[12px] text-destructive">{s.failure_count}</span>
              <span className="font-mono text-[10.5px] text-muted-foreground">
                {s.last_scrape_at ? new Date(s.last_scrape_at).toLocaleDateString() : "—"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Last error per site */}
      {data.sites.some((s) => s.last_error) && (
        <div className="border border-destructive/30 rounded-md bg-destructive/[0.04] px-5 py-4 flex flex-col gap-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-destructive/80">Recent errors</p>
          {data.sites.filter((s) => s.last_error).map((s) => (
            <div key={s.domain} className="flex gap-3 text-[12px]">
              <span className="font-mono text-muted-foreground shrink-0">{s.domain}</span>
              <span className="text-foreground/80 truncate">{s.last_error}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Scraping Tab ───────────────────────────────────────────────────────────

function ScrapingTab() {
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [rules, setRules] = useState<AdminScrapingRule | null>(null);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [regenLoading, setRegenLoading] = useState<string | null>(null);
  // Domains actively scraping: maps domain → last_scrape_at snapshot before trigger
  const [scrapingDomains, setScrapingDomains] = useState<Record<string, string | null>>({});

  const refreshHealth = useCallback(() =>
    api.admin.health().then(setHealth), []);

  useEffect(() => {
    refreshHealth().finally(() => setLoadingHealth(false));
  }, [refreshHealth]);

  // Poll every 8s while any domain is scraping; detect completion via last_scrape_at change
  useEffect(() => {
    if (Object.keys(scrapingDomains).length === 0) return;
    const interval = setInterval(async () => {
      const updated = await api.admin.health().catch(() => null);
      if (!updated) return;
      setHealth(updated);
      setScrapingDomains((prev) => {
        const next = { ...prev };
        for (const domain of Object.keys(prev)) {
          const site = updated.sites.find((s) => s.domain === domain);
          const newTime = site?.last_scrape_at ?? null;
          if (newTime !== prev[domain]) {
            toast.success(`Scraping finished for ${domain}`);
            delete next[domain];
          }
        }
        return next;
      });
    }, 8000);
    return () => clearInterval(interval);
  }, [scrapingDomains]);

  const handleViewRules = (domain: string) => {
    setSelectedDomain(domain);
    setRules(null);
    setRulesLoading(true);
    api.admin.rules(domain)
      .then(setRules)
      .catch(() => toast.error(`No rules for ${domain}`))
      .finally(() => setRulesLoading(false));
  };

  const handleScrape = async (domain: string) => {
    const currentTime = health?.sites.find((s) => s.domain === domain)?.last_scrape_at ?? null;
    try {
      await api.admin.triggerScrape(domain);
      setScrapingDomains((prev) => ({ ...prev, [domain]: currentTime }));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast.error(msg);
    }
  };

  const handleRegen = async (domain: string) => {
    setRegenLoading(domain);
    try {
      await api.admin.regenerateRules(domain);
      toast.success(`AI rule regeneration queued for ${domain}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast.error(msg);
    } finally {
      setRegenLoading(null);
    }
  };

  if (loadingHealth) return <LoadingState label="Loading sites" />;

  return (
    <div className="flex flex-col gap-5">
      <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
        <div className="grid grid-cols-[1fr_auto] gap-3 px-5 py-3 border-b border-border bg-surface/60">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Domain</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Actions</span>
        </div>
        <div className="divide-y divide-border">
          {(health?.sites ?? []).length === 0 ? (
            <div className="px-5 py-8 text-center">
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">No scraping rules configured.</p>
            </div>
          ) : (health?.sites ?? []).map((s) => (
            <div key={s.domain} className="flex items-center justify-between gap-3 px-5 py-3.5">
              <div>
                <p className="font-mono text-[12.5px] text-foreground">{s.domain}</p>
                <p className="font-mono text-[10px] text-muted-foreground">{s.site_name} · {s.product_count} products</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleViewRules(s.domain)}
                  className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors font-mono"
                >
                  <ChevronRight size={11} /> Rules
                </button>
                <button
                  onClick={() => handleRegen(s.domain)}
                  disabled={regenLoading === s.domain}
                  className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded border border-border text-[11px] text-amber-500 hover:text-amber-400 hover:border-amber-500/40 transition-colors font-mono disabled:opacity-50"
                >
                  <Sparkles size={11} />
                  {regenLoading === s.domain ? "…" : "Regen"}
                </button>
                <button
                  onClick={() => handleScrape(s.domain)}
                  disabled={s.domain in scrapingDomains}
                  className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded bg-foreground text-background text-[11px] font-medium font-mono hover:bg-foreground/90 transition-colors disabled:opacity-60"
                >
                  {s.domain in scrapingDomains ? (
                    <>
                      <Loader size={11} className="animate-spin" />
                      Scraping…
                    </>
                  ) : (
                    <>
                      <PlayCircle size={11} />
                      Scrape now
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rules viewer */}
      {selectedDomain && (
        <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-border bg-surface/60 flex items-center justify-between">
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              Rules · {selectedDomain}
            </p>
            <button onClick={() => setSelectedDomain(null)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground">
              ✕ close
            </button>
          </div>
          {rulesLoading ? (
            <LoadingState label="Loading rules" height="h-[120px]" />
          ) : rules ? (
            <div className="divide-y divide-border">
              {(Object.entries(rules) as [string, string | number | null][])
                .filter(([k]) => k.endsWith("_css") || k === "domain" || k === "site_name")
                .map(([k, v]) => (
                  <div key={k} className="grid grid-cols-[160px_1fr] gap-3 px-5 py-2.5 items-start">
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground pt-0.5">{k}</span>
                    <span className="font-mono text-[11.5px] text-foreground break-all">{v ?? "—"}</span>
                  </div>
                ))}
            </div>
          ) : null}
        </div>
      )}

      {/* Log stream */}
      <LogPanel />
    </div>
  );
}

function LogPanel() {
  const [data, setData] = useState<AdminLogsResponse | null>(null);
  const [initialLoading, setInitialLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);

  const load = useCallback((isInitial = false) => {
    if (isInitial) setInitialLoading(true);
    api.admin.logs(100)
      .then((d) => {
        setData(d);
        // scroll to bottom so newest lines are visible
        requestAnimationFrame(() => {
          if (preRef.current) preRef.current.scrollTop = preRef.current.scrollHeight;
        });
      })
      .catch(() => {})
      .finally(() => { if (isInitial) setInitialLoading(false); });
  }, []);

  const toggle = () => {
    if (!open) load(true);
    setOpen((v) => !v);
  };

  // auto-refresh every 2s while panel is open
  useEffect(() => {
    if (!open) return;
    const id = setInterval(() => load(false), 2000);
    return () => clearInterval(id);
  }, [open, load]);

  return (
    <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-3 hover:bg-surface/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <ScrollText size={14} className="text-muted-foreground" />
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Log stream (last 100 lines)</span>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{open ? "▲ hide" : "▼ show"}</span>
      </button>
      {open && (
        <div className="border-t border-border">
          {initialLoading ? (
            <LoadingState label="Loading logs" height="h-[80px]" />
          ) : (
            <pre
              ref={preRef}
              className="px-5 py-4 text-[11px] font-mono text-muted-foreground overflow-x-auto overflow-y-auto leading-relaxed resize-y"
              style={{ height: "320px", minHeight: "180px", maxHeight: "80vh" }}
            >
              {(data?.lines ?? ["[no logs]"]).join("\n")}
            </pre>
          )}
          <div className="px-5 py-2.5 border-t border-border flex items-center justify-between">
            <span className="font-mono text-[10px] text-muted-foreground">
              showing last {data?.lines.length ?? 0} of {data?.total ?? 0} entries · drag bottom edge to resize
            </span>
            <button onClick={() => load(false)} className="font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors">
              ↻ refresh
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Data Quality Tab ───────────────────────────────────────────────────────

function QualityTab() {
  const [data, setData] = useState<AdminDataQuality | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.admin.dataQuality()
      .then(setData)
      .catch((e) => setError(e?.message ?? "Failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingState label="Loading quality metrics" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return null;

  const rows = [
    {
      label: "Total products",
      value: data.total_products,
      note: "",
      tone: "neutral",
    },
    {
      label: "Total price events",
      value: data.total_price_events,
      note: "",
      tone: "neutral",
    },
    {
      label: "Missing images",
      value: data.products_without_image,
      note: `${((data.products_without_image / Math.max(data.total_products, 1)) * 100).toFixed(1)}% of catalog`,
      tone: data.products_without_image === 0 ? "success" : "warning",
    },
    {
      label: "No price history",
      value: data.products_without_history,
      note: `${((data.products_without_history / Math.max(data.total_products, 1)) * 100).toFixed(1)}% of catalog`,
      tone: data.products_without_history === 0 ? "success" : "warning",
    },
    {
      label: "Ungrouped products",
      value: data.products_ungrouped,
      note: `${((data.products_ungrouped / Math.max(data.total_products, 1)) * 100).toFixed(1)}% of catalog`,
      tone: data.products_ungrouped === 0 ? "success" : "warning",
    },
  ] as const;

  return (
    <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
      <div className="divide-y divide-border">
        {rows.map(({ label, value, note, tone }) => (
          <div key={label} className="flex items-center justify-between px-5 py-4 gap-4">
            <div className="flex items-center gap-3">
              {tone === "success" ? (
                <CheckCircle size={14} className="text-[hsl(var(--success))] shrink-0" />
              ) : tone === "warning" && value > 0 ? (
                <XCircle size={14} className="text-amber-500 shrink-0" />
              ) : (
                <div className="w-3.5 h-3.5" />
              )}
              <span className="text-[13px] text-foreground">{label}</span>
            </div>
            <div className="flex items-baseline gap-2.5 shrink-0">
              <span className={cn(
                "font-mono font-semibold tabular-nums text-[16px]",
                tone === "success" ? "text-[hsl(var(--success))]" :
                tone === "warning" && value > 0 ? "text-amber-400" : "text-foreground"
              )}>
                {value.toLocaleString()}
              </span>
              {note && (
                <span className="font-mono text-[10.5px] text-muted-foreground">{note}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Users Tab ──────────────────────────────────────────────────────────────

function UsersTab() {
  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.admin.users()
      .then(setUsers)
      .catch((e) => setError(e?.message ?? "Failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleActive = async (user: AdminUserRead) => {
    setActionId(user.id);
    try {
      const updated = await api.admin.updateUser(user.id, { is_active: !user.is_active });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      toast.success(updated.is_active ? `${updated.email} reactivated` : `${updated.email} deactivated`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed";
      toast.error(msg);
    } finally {
      setActionId(null);
    }
  };

  if (loading) return <LoadingState label="Loading users" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
      <div className="grid grid-cols-[1fr_80px_64px_90px_auto] gap-3 px-5 py-3 border-b border-border bg-surface/60">
        {["Email / Name", "Joined", "Favs", "Status", "Action"].map((h) => (
          <span key={h} className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{h}</span>
        ))}
      </div>
      <div className="divide-y divide-border">
        {users.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">No users yet.</p>
          </div>
        ) : users.map((u) => (
          <div key={u.id} className="grid grid-cols-[1fr_80px_64px_90px_auto] gap-3 px-5 py-3.5 items-center">
            <div className="min-w-0">
              <p className="text-[13px] text-foreground truncate">{u.email}</p>
              <p className="font-mono text-[10px] text-muted-foreground truncate">
                {u.full_name ?? "—"}
                {u.is_admin && <span className="ml-1.5 text-amber-400">admin</span>}
              </p>
            </div>
            <span className="font-mono text-[11px] text-muted-foreground">
              {new Date(u.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
            </span>
            <span className="font-mono tabular-nums text-[12px] text-foreground">{u.favorites_count}</span>
            <span className={cn(
              "inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded-full border whitespace-nowrap justify-self-start",
              u.is_active
                ? "text-[hsl(var(--success))] border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/[0.06]"
                : "text-muted-foreground border-border bg-surface-2"
            )}>
              {u.is_active ? "active" : "disabled"}
            </span>
            <button
              onClick={() => toggleActive(u)}
              disabled={actionId === u.id || u.is_admin}
              title={u.is_admin ? "Cannot modify admin accounts" : ""}
              className={cn(
                "h-7 px-2.5 rounded border text-[11px] font-mono transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
                u.is_active
                  ? "border-destructive/30 text-destructive hover:border-destructive hover:bg-destructive/[0.06]"
                  : "border-[hsl(var(--success))]/30 text-[hsl(var(--success))] hover:border-[hsl(var(--success))] hover:bg-[hsl(var(--success))]/[0.06]"
              )}
            >
              {actionId === u.id ? <RefreshCw size={11} className="animate-spin" /> : u.is_active ? "Deactivate" : "Reactivate"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── AdminPanel page ────────────────────────────────────────────────────────

export default function AdminPanel() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [tab, setTab] = useState<Tab>("health");

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <div className="hidden md:block">
        <DashboardSidebar onSettingsClick={() => navigate("/settings")} />
      </div>

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto pb-16 md:pb-0">
        {/* Page header */}
        <div className="border-b border-border px-7 pt-7 pb-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-amber-500/80 mb-1.5">
            · Developer console
          </p>
          <h1 className="font-['Inter'] font-semibold text-foreground text-[28px] tracking-[-0.015em]">
            Admin Panel
          </h1>
          <p className="text-[13px] text-muted-foreground mt-1.5 max-w-2xl">
            System health, scraping control, data quality, and user management. Admin access only.
          </p>
        </div>

        {/* Tab bar */}
        <div className="border-b border-border px-7 flex items-center gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                "inline-flex items-center gap-2 h-11 px-3 border-b-2 font-mono text-[11.5px] tracking-wider transition-colors",
                tab === id
                  ? "border-amber-400 text-amber-400"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon size={13} strokeWidth={1.75} />
              {label.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 px-7 py-8">
          {tab === "health" && <HealthTab />}
          {tab === "scraping" && <ScrapingTab />}
          {tab === "quality" && <QualityTab />}
          {tab === "users" && <UsersTab />}
        </div>
      </div>

      {isMobile && <MobileBottomNav />}
    </div>
  );
}
