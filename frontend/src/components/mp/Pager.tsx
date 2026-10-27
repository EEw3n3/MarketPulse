import { useT } from "@/i18n";

function pages(cur: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const a = Math.max(2, cur - 1);
  const b = Math.min(total - 1, cur + 1);
  if (a > 2) out.push("…");
  for (let i = a; i <= b; i++) out.push(i);
  if (b < total - 1) out.push("…");
  out.push(total);
  return out;
}

export default function Pager({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  const t = useT();
  if (total <= 1) return null;
  return (
    <div className="pages">
      <button type="button" disabled={page <= 1} aria-label={t.common.prevPage} onClick={() => onPage(page - 1)}>
        ‹
      </button>
      {pages(page, total).map((p, i) =>
        p === "…" ? (
          <span key={`e${i}`} aria-hidden="true">
            …
          </span>
        ) : (
          <button key={p} type="button" aria-current={p === page ? "page" : undefined} onClick={() => onPage(p)}>
            {p}
          </button>
        ),
      )}
      <button type="button" disabled={page >= total} aria-label={t.common.nextPage} onClick={() => onPage(page + 1)}>
        ›
      </button>
    </div>
  );
}
