import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { api, type CatalogCard } from "@/lib/api";
import { eur } from "@/lib/format";
import { fieldStyle, shopOf } from "@/lib/shops";
import { useT } from "@/i18n";
import Img from "./Img";

export function spec(c: { concentration?: string | null; volume?: string | null }): string {
  return [c.concentration, c.volume].filter(Boolean).join(" · ");
}

/** Search field with live suggestions from the catalogue. Enter opens the
 *  highlighted perfume, or the catalogue with the query when nothing is highlighted. */
export default function SearchBox({
  variant = "top",
  initial = "",
  onSubmit,
}: {
  variant?: "top" | "big" | "hero";
  initial?: string;
  onSubmit?: (q: string) => void;
}) {
  const t = useT();
  const nav = useNavigate();
  const id = useId();
  const [q, setQ] = useState(initial);
  const [hits, setHits] = useState<CatalogCard[] | null>(null);
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(-1);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => setQ(initial), [initial]);

  useEffect(() => {
    const v = q.trim();
    if (v.length < 2) {
      setHits(null);
      return;
    }
    let live = true;
    const h = setTimeout(() => {
      api
        .getCards({ search: v, limit: 6, sort: "shops" })
        .then((r) => {
          if (live) {
            setHits(r.items);
            setSel(-1);
          }
        })
        .catch(() => live && setHits([]));
    }, 180);
    return () => {
      live = false;
      clearTimeout(h);
    };
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  function submit() {
    setOpen(false);
    if (sel > -1 && hits?.[sel]) {
      nav(`/product/${hits[sel].product_id}`);
      return;
    }
    if (onSubmit) onSubmit(q.trim());
    else nav(`/catalog?q=${encodeURIComponent(q.trim())}`);
  }

  const show = open && q.trim().length >= 2 && hits !== null;
  const placeholder = variant === "big" ? t.catalog.searchPlaceholder : variant === "hero" ? t.landing.find : t.shell.searchPlaceholder;
  const input = (
    <input
      type="search"
      value={q}
      aria-label={placeholder}
      autoComplete="off"
      placeholder={placeholder}
      role="combobox"
      aria-expanded={show}
      aria-controls={`${id}-sug`}
      aria-activedescendant={sel > -1 ? `${id}-${sel}` : undefined}
      onChange={(e) => {
        setQ(e.target.value);
        setOpen(true);
      }}
      onFocus={() => setOpen(true)}
      onKeyDown={(e) => {
        if (e.key === "Escape") return setOpen(false);
        if (!hits?.length) return;
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          setOpen(true);
          setSel((s) => (e.key === "ArrowDown" ? (s + 1) % hits.length : (s - 1 + hits.length) % hits.length));
        }
      }}
    />
  );

  const box = show && (
    <div className="suggest" id={`${id}-sug`} role="listbox" aria-label={t.shell.matching}>
      {hits!.length === 0 && <p className="sug-empty">{t.shell.noMatch}</p>}
      {hits!.map((c, i) => (
        <a
          key={c.key}
          id={`${id}-${i}`}
          className="sug"
          role="option"
          aria-selected={i === sel}
          href={`/product/${c.product_id}`}
          onClick={(e) => {
            e.preventDefault();
            setOpen(false);
            nav(`/product/${c.product_id}`);
          }}
          onMouseEnter={() => setSel(i)}
        >
          <span className="sw" style={fieldStyle(c.cheapest_store)}>
            <Img src={c.image_url} brand={c.brand} />
          </span>
          <span style={{ minWidth: 0 }}>
            <b>
              {c.brand} {c.name}
            </b>
            <small>{spec(c)}</small>
          </span>
          <span className="p num">
            {eur(c.min_price)}
            <small>{shopOf(c.cheapest_store).label}</small>
          </span>
        </a>
      ))}
      {hits!.length > 0 && (
        <a
          className="sug-all"
          href={`/catalog?q=${encodeURIComponent(q.trim())}`}
          onClick={(e) => {
            e.preventDefault();
            setSel(-1);
            setOpen(false);
            if (onSubmit) onSubmit(q.trim());
            else nav(`/catalog?q=${encodeURIComponent(q.trim())}`);
          }}
        >
          {t.shell.allResults(q.trim())}
        </a>
      )}
    </div>
  );

  if (variant === "big" || variant === "hero") {
    return (
      <div className={variant === "big" ? "bigfind" : "search"} ref={wrap}>
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {variant === "big" && <Search size={18} aria-hidden="true" />}
          {input}
          <button className="btn btn-accent" type="submit">
            {variant === "big" ? t.common.search : t.landing.compare}
          </button>
        </form>
        {box}
      </div>
    );
  }
  return (
    <div className="find" ref={wrap}>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label>
          <Search size={16} aria-hidden="true" />
          {input}
        </label>
      </form>
      {box}
    </div>
  );
}
