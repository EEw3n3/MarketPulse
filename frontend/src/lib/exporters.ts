/**
 * Client-side exporters for CSV/JSON (no external libraries).
 *
 * Excel and PDF are generated on the backend — see app/api/exports.py.
 * For those we just build a URL and let the browser fetch it as a download.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL as string;
const TOKEN_KEY = "marketpulse_token";

export type ExportFormat = "csv" | "xlsx" | "pdf" | "json";

// Period labels in UI ↔ backend period codes
export const PERIOD_TO_CODE: Record<string, "1w" | "1m" | "3m" | "6m" | "1y" | "all"> = {
  "1 Week": "1w",
  "1 Month": "1m",
  "3 Months": "3m",
  "6 Months": "6m",
  "1 Year": "1y",
  "All Time": "all",
};

export function periodToDays(code: string): number | null {
  switch (code) {
    case "1w": return 7;
    case "1m": return 30;
    case "3m": return 90;
    case "6m": return 180;
    case "1y": return 365;
    default: return null; // all
  }
}

// ── CSV ──────────────────────────────────────────────────────────────────────

function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const s = String(value);
  // Quote if contains comma, quote, or newline
  if (/[",\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function exportCsv(
  rows: Record<string, unknown>[],
  filename: string,
  headerOrder?: string[],
  metadata?: string[],
): void {
  const lines: string[] = [];
  // Commented metadata block (lines prefixed with `# `) — Excel ignores these
  // visually if comma-separated, but they're still human-readable on inspection.
  if (metadata && metadata.length) {
    for (const m of metadata) lines.push(`# ${m}`);
    lines.push(""); // blank separator before table
  }
  if (!rows.length) {
    lines.push("No data");
    triggerDownload(new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" }), filename);
    return;
  }
  const headers = headerOrder ?? Object.keys(rows[0]);
  lines.push(headers.map(escapeCsvCell).join(","));
  for (const row of rows) {
    lines.push(headers.map(h => escapeCsvCell(row[h])).join(","));
  }
  // UTF-8 BOM so Excel opens cyrillic/accented chars correctly
  const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  triggerDownload(blob, filename);
}

// ── JSON ─────────────────────────────────────────────────────────────────────

export function exportJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  triggerDownload(blob, filename);
}

// ── Backend download (xlsx / pdf) ────────────────────────────────────────────

interface ProductExportParams {
  productId: number;
  format: "xlsx" | "pdf";
  period: string; // backend code
}

interface CatalogExportParams {
  format: "xlsx" | "pdf";
  search?: string;
  brands?: string[];
  stores?: string[];
}

function buildQuery(params: Record<string, string | string[] | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) v.forEach(item => p.append(k, item));
    else p.set(k, v);
  }
  return p.toString();
}

/** Downloads xlsx/pdf via authenticated fetch — token-bearing endpoints
 *  cannot be opened with plain window.location (no header support). */
async function downloadAuthenticated(url: string, filename: string): Promise<void> {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Export failed: ${res.status} ${res.statusText}`);
  const blob = await res.blob();
  triggerDownload(blob, filename);
}

export async function exportProductBackend(p: ProductExportParams, suggestedName: string): Promise<void> {
  const qs = buildQuery({ format: p.format, period: p.period });
  const url = `${API_BASE_URL}/exports/products/${p.productId}?${qs}`;
  await downloadAuthenticated(url, `${suggestedName}.${p.format}`);
}

export async function exportCatalogBackend(p: CatalogExportParams, suggestedName: string): Promise<void> {
  const qs = buildQuery({
    format: p.format,
    search: p.search,
    brands: p.brands,
    stores: p.stores,
  });
  const url = `${API_BASE_URL}/exports/catalog?${qs}`;
  await downloadAuthenticated(url, `${suggestedName}.${p.format}`);
}

// ── Internal: trigger browser download via anchor click ─────────────────────

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Give the browser a tick to start the download before revoking
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── Sanitization ─────────────────────────────────────────────────────────────

export function safeFilename(s: string, maxLen = 60): string {
  const cleaned = s.replace(/[^a-zA-Z0-9._\- ]+/g, "_").trim();
  return (cleaned.slice(0, maxLen) || "export").replace(/\.+$/, "");
}
