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
  Trash2,
} from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
  const [worker, setWorker] = useState<{ online: boolean; last_seen_ago_s: number | null; queue_depth: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.admin.health()
      .then(setData)
      .catch((e) => setError(e?.message ?? "Failed to load health"))
      .finally(() => setLoading(false));
    api.admin.workerStatus().then(setWorker).catch(() => setWorker(null));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Refresh worker status every 5s — it's our "is the laptop running" signal
  useEffect(() => {
    const id = setInterval(() => {
      api.admin.workerStatus().then(setWorker).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, []);

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

      {/* Worker status — distributed scrape worker (runs on user's laptop) */}
      <div className="border border-border rounded-md bg-surface/40 px-5 py-4 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              worker?.online ? "bg-[hsl(var(--success))] animate-pulse" : "bg-muted-foreground/40"
            )}
          />
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            Scrape worker
          </span>
          <span className="font-mono text-[12px] text-foreground">
            {worker?.online ? "Online" : "Offline"}
          </span>
        </div>
        {worker?.last_seen_ago_s != null && (
          <span className="font-mono text-[10.5px] text-muted-foreground">
            last seen {worker.last_seen_ago_s}s ago
          </span>
        )}
        <span className="font-mono text-[10.5px] text-muted-foreground ml-auto">
          queue: <span className="text-foreground">{worker?.queue_depth ?? 0}</span>
        </span>
      </div>

      {/* Sites table */}
      <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
        <div className="grid grid-cols-[1fr_90px_120px_90px_90px_110px] gap-4 px-5 py-3 border-b border-border bg-surface/60">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Domain</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground text-right">Products</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Health</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground text-right">Success</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground text-right">Failure</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground text-right">Last scrape</span>
        </div>
        <div className="divide-y divide-border">
          {data.sites.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">No scraping rules found.</p>
            </div>
          ) : data.sites.map((s) => (
            <div key={s.domain} className="grid grid-cols-[1fr_90px_120px_90px_90px_110px] gap-4 px-5 py-3 items-center">
              <div className="min-w-0">
                <p className="font-mono text-[12px] text-foreground truncate">{s.domain}</p>
                <p className="font-mono text-[10px] text-muted-foreground truncate">{s.site_name}</p>
              </div>
              <span className="font-mono tabular-nums text-[12px] text-foreground text-right">{s.product_count}</span>
              <div className="flex items-center gap-1.5">
                <div className="flex-1 h-1 bg-surface-2 rounded-full overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", s.health_score > 0.7 ? "bg-[hsl(var(--success))]" : s.health_score > 0.4 ? "bg-amber-500" : "bg-destructive")}
                    style={{ width: `${s.health_score * 100}%` }}
                  />
                </div>
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground shrink-0 w-8 text-right">
                  {(s.health_score * 100).toFixed(0)}%
                </span>
              </div>
              <span className="font-mono tabular-nums text-[12px] text-[hsl(var(--success))] text-right">{s.success_count}</span>
              <span className="font-mono tabular-nums text-[12px] text-destructive text-right">{s.failure_count}</span>
              <span className="font-mono text-[10.5px] text-muted-foreground text-right">
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

const LIMIT_OPTIONS: { label: string; value: number | null }[] = [
  { label: "50", value: 50 },
  { label: "100", value: 100 },
  { label: "500", value: 500 },
  { label: "1000", value: 1000 },
  { label: "Unlimited", value: null },
];

function ScrapingTab() {
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [rules, setRules] = useState<AdminScrapingRule | null>(null);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [regenLoading, setRegenLoading] = useState<string | null>(null);
  // Domains actively scraping: maps domain → { snapshot, startedAt }
  // - snapshot: last_scrape_at value at trigger time, used to detect completion
  // - startedAt: ms since epoch when trigger fired, used as a stuck-state safety timeout
  const [scrapingDomains, setScrapingDomains] = useState<
    Record<string, { snapshot: string | null; startedAt: number }>
  >({});
  const SCRAPING_MAX_MS = 6 * 60 * 1000; // 6 min hard cap on "Scraping..." UI state
  // Per-site limit chosen via dropdown — null means Unlimited
  const [perSiteLimit, setPerSiteLimit] = useState<Record<string, number | null>>({});
  // Master limit applied by "Scrape All Sites" button
  const [masterLimit, setMasterLimit] = useState<number | null>(100);
  const [scrapingAll, setScrapingAll] = useState(false);

  const refreshHealth = useCallback(() =>
    api.admin.health().then(setHealth), []);

  useEffect(() => {
    refreshHealth().finally(() => setLoadingHealth(false));
  }, [refreshHealth]);

  // Poll every 8s while any domain is scraping; detect completion via last_scrape_at change
  // OR via stuck-state timeout (failed scrapes / 429 don't update last_scrape_at, so without
  // the timeout the UI would spin forever).
  useEffect(() => {
    if (Object.keys(scrapingDomains).length === 0) return;
    const interval = setInterval(async () => {
      const updated = await api.admin.health().catch(() => null);
      if (updated) setHealth(updated);
      setScrapingDomains((prev) => {
        const next = { ...prev };
        const now = Date.now();
        for (const domain of Object.keys(prev)) {
          const { snapshot, startedAt } = prev[domain];
          const site = updated?.sites.find((s) => s.domain === domain);
          const newTime = site?.last_scrape_at ?? null;
          if (updated && newTime !== snapshot) {
            toast.success(`Scraping finished for ${domain}`);
            delete next[domain];
            continue;
          }
          if (now - startedAt > SCRAPING_MAX_MS) {
            toast.error(`${domain} stuck >6 min — clearing UI. Check worker logs.`);
            delete next[domain];
          }
        }
        return next;
      });
    }, 8000);
    return () => clearInterval(interval);
  }, [scrapingDomains]);

  const clearScrapingState = () => {
    setScrapingDomains({});
    toast.success("Cleared scraping state");
  };

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
    const limit = perSiteLimit[domain] === undefined ? 100 : perSiteLimit[domain];
    try {
      await api.admin.triggerScrape(domain, limit);
      setScrapingDomains((prev) => ({
        ...prev,
        [domain]: { snapshot: currentTime, startedAt: Date.now() },
      }));
      toast.success(`Queued ${domain} (limit=${limit ?? "unlimited"})`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast.error(msg);
    }
  };

  const handleScrapeAll = async () => {
    const sites = health?.sites ?? [];
    if (!sites.length) return;
    const confirmMsg = `Start scraping ALL ${sites.length} sites with limit=${masterLimit ?? "unlimited"}?\n\n` +
      `Worker must be running locally. Jobs will be processed in parallel (concurrency=5).`;
    if (!window.confirm(confirmMsg)) return;

    setScrapingAll(true);
    const snapshots: Record<string, string | null> = {};
    for (const s of sites) snapshots[s.domain] = s.last_scrape_at ?? null;

    try {
      const results = await Promise.allSettled(
        sites.map((s) => api.admin.triggerScrape(s.domain, masterLimit))
      );
      const okDomains: string[] = [];
      const failures: { domain: string; reason: string }[] = [];
      results.forEach((r, idx) => {
        const domain = sites[idx].domain;
        if (r.status === "fulfilled") {
          okDomains.push(domain);
        } else {
          const msg = r.reason instanceof Error ? r.reason.message : String(r.reason);
          failures.push({ domain, reason: msg });
        }
      });
      // Only mark successfully-queued domains as scraping. Failed ones (429, etc) shouldn't
      // spin in the UI. Replace any prior state for these domains with a fresh startedAt.
      const startedAt = Date.now();
      setScrapingDomains((prev) => {
        const next = { ...prev };
        for (const d of okDomains) {
          next[d] = { snapshot: snapshots[d], startedAt };
        }
        return next;
      });
      if (failures.length === 0) {
        toast.success(`All ${okDomains.length} scrape jobs queued — check worker logs`);
      } else {
        const failList = failures
          .map((f) => `${f.domain}: ${f.reason.replace(/^API Error:\s*/, "")}`)
          .join("\n");
        toast.error(
          `Queued ${okDomains.length}/${results.length}. Failed:\n${failList}`,
          { duration: 8000 }
        );
      }
    } finally {
      setScrapingAll(false);
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
      {/* Master "Scrape All Sites" block — enqueues 5 jobs in parallel */}
      <div className="border border-border rounded-md bg-surface/40 px-5 py-4 flex flex-wrap items-center gap-3">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Scrape all sites</span>
          <span className="font-mono text-[11px] text-foreground/70">
            Queues a job per site for the local worker (parallel, concurrency=5)
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <label className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground">
            Master limit:
          </label>
          <select
            value={masterLimit === null ? "unlimited" : String(masterLimit)}
            onChange={(e) =>
              setMasterLimit(e.target.value === "unlimited" ? null : parseInt(e.target.value, 10))
            }
            className="h-7 px-2 rounded border border-border bg-background text-[11.5px] font-mono text-foreground"
          >
            {LIMIT_OPTIONS.map((opt) => (
              <option key={opt.label} value={opt.value === null ? "unlimited" : String(opt.value)}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleScrapeAll}
            disabled={scrapingAll || (health?.sites ?? []).length === 0}
            className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded bg-primary text-primary-foreground text-[12px] font-semibold font-mono hover:brightness-110 transition-all disabled:opacity-60"
          >
            {scrapingAll ? (
              <>
                <Loader size={12} className="animate-spin" /> Queueing…
              </>
            ) : (
              <>
                <PlayCircle size={12} /> Scrape All {(health?.sites ?? []).length} Sites
              </>
            )}
          </button>
          {Object.keys(scrapingDomains).length > 0 && (
            <button
              onClick={clearScrapingState}
              title="Force-clear the spinning 'Scraping…' UI state for all domains. Use when a scrape was rejected (429) or failed silently and the buttons are stuck."
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded border border-amber-500/40 text-[11.5px] font-mono text-amber-300/90 hover:bg-amber-500/10 transition-colors"
            >
              Clear ({Object.keys(scrapingDomains).length})
            </button>
          )}
        </div>
      </div>

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
          ) : (health?.sites ?? []).map((s) => {
            const limit = perSiteLimit[s.domain] === undefined ? 100 : perSiteLimit[s.domain];
            return (
            <div key={s.domain} className="flex items-center justify-between gap-3 px-5 py-3.5">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <p className="font-mono text-[12.5px] text-foreground">{s.domain}</p>
                  {s.product_count === 0 && (
                    <span
                      title="Cloudflare Managed Challenge blocks our worker on this site. Integration in progress — paid solver or undetected-chromedriver planned."
                      className="font-mono text-[9.5px] uppercase tracking-[0.12em] px-1.5 py-0.5 rounded border border-amber-500/40 text-amber-400 bg-amber-500/10"
                    >
                      Blocked · in progress
                    </span>
                  )}
                </div>
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
                <select
                  value={limit === null ? "unlimited" : String(limit)}
                  onChange={(e) =>
                    setPerSiteLimit((prev) => ({
                      ...prev,
                      [s.domain]: e.target.value === "unlimited" ? null : parseInt(e.target.value, 10),
                    }))
                  }
                  disabled={s.domain in scrapingDomains}
                  className="h-7 px-2 rounded border border-border bg-background text-[11px] font-mono text-foreground disabled:opacity-50"
                  title="Scrape limit"
                >
                  {LIMIT_OPTIONS.map((opt) => (
                    <option key={opt.label} value={opt.value === null ? "unlimited" : String(opt.value)}>
                      {opt.label}
                    </option>
                  ))}
                </select>
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
          );})}
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
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [userToDelete, setUserToDelete] = useState<AdminUserRead | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [batching, setBatching] = useState(false);

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

  const toggleSelect = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const selectableIds = users.filter((u) => !u.is_admin).map((u) => u.id);
  const allChecked = selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));
  const toggleAll = () =>
    setSelected(allChecked ? new Set() : new Set(selectableIds));

  const handleBatchDeactivate = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Deactivate ${selected.size} selected user(s)?`)) return;
    setBatching(true);
    try {
      const res = await api.admin.batchDeactivate(Array.from(selected));
      toast.success(
        `Deactivated ${res.updated}` +
        (res.skipped_self > 0 ? ` (skipped self)` : "")
      );
      setSelected(new Set());
      load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Batch deactivate failed");
    } finally {
      setBatching(false);
    }
  };

  const handleDelete = async () => {
    if (!userToDelete) return;
    setDeleting(true);
    try {
      await api.admin.deleteUser(userToDelete.id);
      setUsers((prev) => prev.filter((u) => u.id !== userToDelete.id));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(userToDelete.id);
        return next;
      });
      toast.success(`Deleted ${userToDelete.email}`);
      setUserToDelete(null);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingState label="Loading users" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <>
      {/* Batch action bar — appears when any row selected */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-3 px-4 py-2.5 rounded-md border border-amber-500/30 bg-amber-500/[0.06]">
          <span className="font-mono text-[11.5px] text-amber-400">
            {selected.size} selected
          </span>
          <button
            onClick={handleBatchDeactivate}
            disabled={batching}
            className="ml-auto h-7 px-3 rounded text-[11px] font-mono border border-destructive/40 text-destructive hover:bg-destructive/[0.08] transition-colors disabled:opacity-50"
          >
            {batching ? "…" : "Deactivate selected"}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="h-7 px-3 rounded text-[11px] font-mono border border-border text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        </div>
      )}

      <div className="border border-border rounded-md bg-surface/40 overflow-hidden">
        <div className="grid grid-cols-[28px_1fr_80px_64px_90px_auto] gap-3 px-5 py-3 border-b border-border bg-surface/60">
          <input
            type="checkbox"
            checked={allChecked}
            onChange={toggleAll}
            className="accent-primary"
            title="Select all (non-admin) users"
          />
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
            <div key={u.id} className="grid grid-cols-[28px_1fr_80px_64px_90px_auto] gap-3 px-5 py-3.5 items-center">
              <input
                type="checkbox"
                checked={selected.has(u.id)}
                disabled={u.is_admin}
                onChange={() => toggleSelect(u.id)}
                className="accent-primary disabled:opacity-30"
                title={u.is_admin ? "Cannot select admin accounts" : ""}
              />
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
              <div className="flex items-center gap-1.5">
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
                <button
                  onClick={() => setUserToDelete(u)}
                  disabled={u.is_admin}
                  title={u.is_admin ? "Cannot delete admin accounts" : "Permanently delete user"}
                  className="h-7 w-7 inline-flex items-center justify-center rounded border border-destructive/30 text-destructive hover:border-destructive hover:bg-destructive/[0.06] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <AlertDialog open={!!userToDelete} onOpenChange={(o) => !o && setUserToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user {userToDelete?.email}?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the user, all their favorites, and preferences.
              The email becomes available for re-registration. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
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
