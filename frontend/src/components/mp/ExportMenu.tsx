import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Lock } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import { download, type ExportFormat } from "@/lib/download";
import { hasPro } from "@/lib/plan";

const FORMATS: ExportFormat[] = ["xlsx", "pdf", "csv", "json"];

/** "Export" button with the four formats. Free users see a lock that leads to
 *  the Pro plan. `path(format)` builds the endpoint with its query string. */
export default function ExportMenu({
  path,
  fallbackName,
  label,
  className = "btn btn-soft btn-sm",
  header,
}: {
  path: (f: ExportFormat) => string;
  fallbackName: string;
  label?: string;
  className?: string;
  header?: ReactNode;
}) {
  const t = useT();
  const { user } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const pro = hasPro(user);

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

  async function run(f: ExportFormat) {
    setBusy(f);
    const id = toast.loading(t.exporter.started);
    try {
      await download(path(f), `${fallbackName}.${f}`);
      toast.success(t.exporter.done, { id });
      setOpen(false);
    } catch {
      toast.error(t.exporter.failed, { id });
    } finally {
      setBusy(null);
    }
  }

  if (!pro) {
    return (
      <button className={className} type="button" onClick={() => nav("/profile#plan")} title={t.pro.lockedExport}>
        <Lock />
        {label ?? t.exporter.button}
        <span className="tag tag-pro">{t.common.pro}</span>
      </button>
    );
  }

  return (
    <div className="xmenu" ref={ref}>
      <button className={className} type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Download />
        {label ?? t.exporter.button}
      </button>
      {open && (
        <div className="menu fade" role="menu">
          {header}
          {FORMATS.map((f) => (
            <button key={f} type="button" role="menuitem" disabled={busy !== null} onClick={() => run(f)}>
              <span>
                {t.exporter.formats[f]}
                <span className="k" style={{ display: "block" }}>
                  {t.exporter.formatHint[f]}
                </span>
              </span>
              <span className="k">{busy === f ? "…" : `.${f}`}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
