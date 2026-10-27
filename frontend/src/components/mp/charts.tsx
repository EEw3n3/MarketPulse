import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { day, eur, eur0, int } from "@/lib/format";
import { shopOf } from "@/lib/shops";

// Small SVG charts in the MarketPulse style: 2px lines, a recessive grid, a
// crosshair with a tooltip on hover or arrow keys, values in the text inks.

function niceStep(raw: number): number {
  if (!(raw > 0)) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

function useWidth<T extends HTMLElement>(min = 280): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(min, Math.floor(e.contentRect.width))));
    ro.observe(el);
    setW(Math.max(min, Math.floor(el.clientWidth)));
    return () => ro.disconnect();
  }, [min]);
  return [ref, w];
}

export interface LineSeries {
  key: string;
  name: string;
  color: string;
  values: (number | null)[];
  width?: number;
}

export function LineChart({
  days,
  series,
  height = 280,
  padLeft = 52,
  yFormat = (v) => eur0(v),
  tipFormat = (v) => eur(v),
  label,
  estimate,
  estimateLabel,
  focus,
  xTicks = 4,
  baseline,
  tipOrder = "asc",
}: {
  days: string[];
  series: LineSeries[];
  height?: number;
  padLeft?: number;
  yFormat?: (v: number) => string;
  tipFormat?: (v: number) => string;
  label: string;
  estimate?: { from: string | null; to: string | null } | null;
  estimateLabel?: string;
  focus?: string | null;
  xTicks?: number;
  baseline?: number;
  tipOrder?: "asc" | "desc";
}) {
  const [host, W] = useWidth<HTMLDivElement>();
  const [cur, setCur] = useState(-1);
  const n = days.length;
  const H = height;
  const padR = 14;
  const padT = 14;
  const padB = 30;

  const scale = useMemo(() => {
    const all: number[] = [];
    series.forEach((s) => s.values.forEach((v) => v != null && all.push(v)));
    if (baseline != null) all.push(baseline);
    if (!all.length) return null;
    let lo = Math.min(...all);
    let hi = Math.max(...all);
    const step = niceStep((hi - lo) / 4 || Math.abs(hi) / 10 || 1);
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;
    if (hi === lo) hi = lo + step;
    const ticks: number[] = [];
    for (let t = lo; t <= hi + 1e-9; t += step) ticks.push(Math.round(t * 1000) / 1000);
    return { lo, hi, ticks };
  }, [series, baseline]);

  if (!scale || n < 2 || !W) {
    return <div ref={host} className="chart" style={{ height: H }} aria-label={label} />;
  }
  const { lo, hi, ticks } = scale;
  const x = (i: number) => padLeft + (i / (n - 1)) * (W - padLeft - padR);
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
  // Date labels need about 90px each; narrow charts get fewer.
  const nx = Math.max(2, Math.min(xTicks, Math.floor((W - padLeft - padR) / 90) + 1));

  const paths = series.map((s) => {
    let d = "";
    let pen = false;
    let last = -1;
    s.values.forEach((v, i) => {
      if (v == null) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
      pen = true;
      last = i;
    });
    return { s, d, last };
  });

  const estFrom = estimate?.from ? days.indexOf(estimate.from) : -1;
  const estTo = estimate?.to ? days.indexOf(estimate.to) : -1;
  const est =
    estimate && (estFrom > -1 || estTo > -1)
      ? { a: x(Math.max(0, estFrom)), b: x(estTo > -1 ? estTo : n - 1) }
      : null;

  const rows =
    cur > -1
      ? series
          .map((s) => ({ s, v: s.values[cur] }))
          .filter((r) => r.v != null)
          .sort((a, b) => (tipOrder === "asc" ? a.v! - b.v! : b.v! - a.v!))
      : [];
  let tipLeft = cur > -1 ? x(cur) + 14 : 0;
  if (tipLeft + 196 > W) tipLeft = x(cur) - 14 - 196;

  const pick = (clientX: number, rect: DOMRect) => {
    const px = (clientX - rect.left) * (W / rect.width);
    setCur(Math.max(0, Math.min(n - 1, Math.round(((px - padLeft) / (W - padLeft - padR)) * (n - 1)))));
  };

  return (
    <div
      ref={host}
      className="chart"
      tabIndex={0}
      aria-label={label}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.preventDefault();
          setCur((c) => Math.max(0, Math.min(n - 1, (c < 0 ? n - 1 : c) + (e.key === "ArrowLeft" ? -1 : 1))));
        } else if (e.key === "Escape") setCur(-1);
      }}
      onBlur={() => setCur(-1)}
    >
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={label}
        style={{ display: "block", overflow: "visible", touchAction: "pan-y" }}
        onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerDown={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerLeave={() => setCur(-1)}
      >
        {est && (
          <g>
            <rect className="c-est" x={est.a} y={padT} width={Math.max(2, est.b - est.a)} height={H - padT - padB} rx={6} />
            {estimateLabel && (
              <text className="c-est-l" x={(est.a + est.b) / 2} y={padT + 14} textAnchor="middle">
                {estimateLabel}
              </text>
            )}
          </g>
        )}
        {ticks.map((t) => (
          <g key={t}>
            <line className={baseline != null && t === baseline ? "c-zero" : "c-grid"} x1={padLeft} x2={W - padR} y1={y(t)} y2={y(t)} />
            {padLeft > 0 && (
              <text className="c-tick" x={padLeft - 10} y={y(t) + 4} textAnchor="end">
                {yFormat(t)}
              </text>
            )}
          </g>
        ))}
        {Array.from({ length: nx }, (_, k) => {
          const i = Math.round((k * (n - 1)) / (nx - 1));
          return (
            <text key={k} className="c-tick" x={x(i)} y={H - 8} textAnchor={k === 0 ? "start" : k === nx - 1 ? "end" : "middle"}>
              {day(days[i])}
            </text>
          );
        })}
        {paths.map(({ s, d, last }, i) => {
          const op = focus && focus !== s.key ? 0.18 : 1;
          return (
            <g key={s.key} opacity={op} className="c-line">
              <path
                className="c-draw"
                style={{ ["--i" as string]: i } as React.CSSProperties}
                pathLength={1}
                d={d}
                fill="none"
                stroke={s.color}
                strokeWidth={s.width ?? 2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {last > -1 && <circle className="c-end" cx={x(last)} cy={y(s.values[last]!)} r={4} fill={s.color} />}
            </g>
          );
        })}
        {cur > -1 && (
          <g>
            <line className="c-cross" x1={x(cur)} x2={x(cur)} y1={padT} y2={H - padB} />
            {series.map((s) =>
              s.values[cur] != null ? <circle key={s.key} className="c-dot" r={5} cx={x(cur)} cy={y(s.values[cur]!)} fill={s.color} /> : null,
            )}
          </g>
        )}
      </svg>
      {cur > -1 && rows.length > 0 && (
        <div className="c-tip" style={{ left: tipLeft, top: padT }}>
          <div className="c-tip-date">{day(days[cur])}</div>
          {rows.map((r) => (
            <div key={r.s.key} className="c-tip-row">
              <span className="c-sw" style={{ background: r.s.color }} />
              <span>{r.s.name}</span>
              <b className="num">{tipFormat(r.v!)}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Legend that doubles as a highlighter: hover or focus a shop to bring its line forward. */
export function Legend({
  items,
  focus,
  onFocus,
}: {
  items: { key: string; name: string; color: string; field?: string; extra?: ReactNode }[];
  focus: string | null;
  onFocus: (k: string | null) => void;
}) {
  return (
    <div className="legend">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          aria-pressed={focus === it.key}
          style={{ ["--line" as string]: it.color, ["--field" as string]: it.field ?? "var(--surface)" } as React.CSSProperties}
          onMouseEnter={() => onFocus(it.key)}
          onMouseLeave={() => onFocus(null)}
          onFocus={() => onFocus(it.key)}
          onBlur={() => onFocus(null)}
          onClick={() => onFocus(focus === it.key ? null : it.key)}
        >
          <i />
          {it.name}
          {it.extra}
        </button>
      ))}
    </div>
  );
}

export function Sparkline({ values, color = "var(--ink)", height = 40 }: { values: (number | null)[]; color?: string; height?: number }) {
  const v = values.map((x, i) => [i, x] as const).filter(([, x]) => x != null) as [number, number][];
  if (v.length < 2) return <svg height={height} aria-hidden="true" />;
  const n = values.length;
  const lo = Math.min(...v.map(([, x]) => x));
  const hi = Math.max(...v.map(([, x]) => x));
  const d = v
    .map(([i, x], k) => `${k ? "L" : "M"}${((i / (n - 1)) * 100).toFixed(2)} ${(height - 3 - (hi === lo ? 0.5 : (x - lo) / (hi - lo)) * (height - 6)).toFixed(2)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" height={height} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth={1.75} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

/** Which shop was cheapest on each day, as a strip of shop colours. */
export function Ribbon({ cheapest, label }: { cheapest: (string | null)[]; label?: string }) {
  return (
    <div className="ribbon" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {cheapest.map((k, i) => (
        <span key={i} style={{ background: k ? shopOf(k).field : "transparent" }} />
      ))}
    </div>
  );
}

/** Daily price changes per shop: cuts below the axis, rises above, stacked by shop. */
export function ActivityBars({
  days,
  points,
  stores,
  height = 240,
  upLabel,
  downLabel,
  label,
}: {
  days: string[];
  points: { date: string; store: string; up: number; down: number }[];
  stores: string[];
  height?: number;
  upLabel: string;
  downLabel: string;
  label: string;
}) {
  const [host, W] = useWidth<HTMLDivElement>();
  const [cur, setCur] = useState(-1);
  const by = useMemo(() => {
    const m = new Map<string, Map<string, { up: number; down: number }>>();
    points.forEach((p) => {
      if (!m.has(p.date)) m.set(p.date, new Map());
      m.get(p.date)!.set(p.store, { up: p.up, down: p.down });
    });
    return m;
  }, [points]);
  const n = days.length;
  const totals = days.map((d) => {
    const m = by.get(d);
    let up = 0;
    let down = 0;
    m?.forEach((v) => {
      up += v.up;
      down += v.down;
    });
    return { up, down };
  });
  const maxUp = Math.max(1, ...totals.map((t) => t.up));
  const maxDown = Math.max(1, ...totals.map((t) => t.down));
  const step = niceStep(Math.max(maxUp, maxDown) / 3);
  const top = Math.ceil(maxUp / step) * step;
  const bot = Math.ceil(maxDown / step) * step;
  const padL = 48;
  const padR = 8;
  const padT = 10;
  const padB = 28;
  const H = height;
  if (!W || !n) return <div ref={host} className="chart" style={{ height: H }} />;
  const plotH = H - padT - padB;
  const zero = padT + (top / (top + bot)) * plotH;
  const unit = plotH / (top + bot);
  const bw = (W - padL - padR) / n;
  const x = (i: number) => padL + i * bw;
  const ticks: number[] = [];
  for (let t = -bot; t <= top + 1e-9; t += step) ticks.push(t);

  let tipLeft = cur > -1 ? x(cur) + bw + 10 : 0;
  if (tipLeft + 200 > W) tipLeft = x(cur) - 210;

  return (
    <div
      ref={host}
      className="chart"
      tabIndex={0}
      aria-label={label}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.preventDefault();
          setCur((c) => Math.max(0, Math.min(n - 1, (c < 0 ? n - 1 : c) + (e.key === "ArrowLeft" ? -1 : 1))));
        } else if (e.key === "Escape") setCur(-1);
      }}
      onBlur={() => setCur(-1)}
    >
      <svg
        width={W}
        height={H}
        role="img"
        aria-label={label}
        style={{ display: "block", overflow: "visible", touchAction: "pan-y" }}
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = (e.clientX - r.left) * (W / r.width);
          setCur(Math.max(0, Math.min(n - 1, Math.floor((px - padL) / bw))));
        }}
        onPointerLeave={() => setCur(-1)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className={t === 0 ? "c-zero" : "c-grid"} x1={padL} x2={W - padR} y1={zero - t * unit} y2={zero - t * unit} />
            <text className="c-tick" x={padL - 10} y={zero - t * unit + 4} textAnchor="end">
              {int(Math.abs(t))}
            </text>
          </g>
        ))}
        <text className="c-tick" x={padL - 10} y={padT - 2} textAnchor="end" style={{ fontSize: 11 }}>
          ↑
        </text>
        {days.map((d, i) => {
          const m = by.get(d);
          let upY = zero;
          let downY = zero;
          const w = Math.max(1, bw - 2);
          return (
            <g key={d} opacity={cur > -1 && cur !== i ? 0.45 : 1}>
              {stores.map((s) => {
                const v = m?.get(s);
                if (!v) return null;
                const out: ReactNode[] = [];
                if (v.up) {
                  const h = v.up * unit;
                  upY -= h;
                  out.push(<rect key="u" x={x(i) + 1} y={upY} width={w} height={Math.max(0, h - 1)} fill={shopOf(s).line} rx={Math.min(3, w / 2)} />);
                }
                if (v.down) {
                  const h = v.down * unit;
                  out.push(<rect key="d" x={x(i) + 1} y={downY + 1} width={w} height={Math.max(0, h - 1)} fill={shopOf(s).line} rx={Math.min(3, w / 2)} />);
                  downY += h;
                }
                return <g key={s}>{out}</g>;
              })}
            </g>
          );
        })}
        {[0, Math.floor((n - 1) / 2), n - 1].map((i, k) => (
          <text key={k} className="c-tick" x={x(i) + bw / 2} y={H - 8} textAnchor={k === 0 ? "start" : k === 2 ? "end" : "middle"}>
            {day(days[i])}
          </text>
        ))}
      </svg>
      {cur > -1 && (
        <div className="c-tip" style={{ left: tipLeft, top: padT }}>
          <div className="c-tip-date">{day(days[cur])}</div>
          {stores.map((s) => {
            const v = by.get(days[cur])?.get(s);
            if (!v || (!v.up && !v.down)) return null;
            return (
              <div key={s} className="c-tip-row">
                <span className="c-sw" style={{ background: shopOf(s).line }} />
                <span>{shopOf(s).label}</span>
                <b className="num">
                  ↓{int(v.down)} ↑{int(v.up)}
                </b>
              </div>
            );
          })}
          <div className="c-tip-row" style={{ marginTop: 4, borderTop: "1px solid #3a3d41", paddingTop: 4 }}>
            <span />
            <span>
              {downLabel} / {upLabel}
            </span>
            <b className="num">
              {int(totals[cur].down)} / {int(totals[cur].up)}
            </b>
          </div>
        </div>
      )}
    </div>
  );
}

/** Histogram of price changes: cuts in green, rises in red. */
export function Histogram({
  bins,
  height = 220,
  label,
  tip,
}: {
  bins: { lower: number; upper: number; count: number }[];
  height?: number;
  label: string;
  tip: (b: { lower: number; upper: number; count: number }) => string;
}) {
  const [host, W] = useWidth<HTMLDivElement>();
  const [cur, setCur] = useState(-1);
  const n = bins.length;
  const H = height;
  const padL = 48;
  const padR = 8;
  const padT = 10;
  const padB = 28;
  if (!W || !n) return <div ref={host} className="chart" style={{ height: H }} />;
  const max = Math.max(1, ...bins.map((b) => b.count));
  const step = niceStep(max / 3);
  const top = Math.ceil(max / step) * step;
  const bw = (W - padL - padR) / n;
  const y = (v: number) => padT + (1 - v / top) * (H - padT - padB);
  const ticks: number[] = [];
  for (let t = 0; t <= top + 1e-9; t += step) ticks.push(t);
  const fmt = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)}%`;
  return (
    <div ref={host} className="chart" aria-label={label}>
      <svg width={W} height={H} role="img" aria-label={label} style={{ display: "block", overflow: "visible" }} onPointerLeave={() => setCur(-1)}>
        {ticks.map((t) => (
          <g key={t}>
            <line className={t === 0 ? "c-zero" : "c-grid"} x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} />
            <text className="c-tick" x={padL - 10} y={y(t) + 4} textAnchor="end">
              {int(t)}
            </text>
          </g>
        ))}
        {bins.map((b, i) => {
          const color = b.upper <= 0 ? "var(--down)" : b.lower >= 0 ? "var(--up)" : "var(--muted)";
          const w = Math.max(1, bw - 2);
          return (
            <g key={i} onPointerEnter={() => setCur(i)}>
              <rect x={padL + i * bw} y={padT} width={bw} height={H - padT - padB} fill="transparent" />
              <rect x={padL + i * bw + 1} y={y(b.count)} width={w} height={Math.max(0, y(0) - y(b.count))} fill={color} opacity={cur > -1 && cur !== i ? 0.45 : 0.85} rx={Math.min(4, w / 2)} />
            </g>
          );
        })}
        {bins.map((b, i) =>
          i % Math.max(1, Math.ceil(n / 8)) === 0 || i === n - 1 ? (
            <text key={i} className="c-tick" x={padL + i * bw + bw / 2} y={H - 8} textAnchor="middle">
              {fmt(i === n - 1 ? b.upper : b.lower)}
            </text>
          ) : null,
        )}
      </svg>
      {cur > -1 && (
        <div className="c-tip" style={{ left: Math.min(W - 200, padL + cur * bw + bw + 8), top: padT }}>
          {tip(bins[cur])}
        </div>
      )}
    </div>
  );
}

export function useReducedMotion(): boolean {
  const [r, setR] = useState(false);
  useEffect(() => {
    const m = matchMedia("(prefers-reduced-motion: reduce)");
    setR(m.matches);
    const on = () => setR(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return r;
}
