import { useState } from "react";
import { Lock } from "lucide-react";
import { useT } from "@/i18n";
import { eur } from "@/lib/format";
import { PRO_PRICE } from "@/lib/plan";
import { SHOPS } from "@/lib/shops";

const LINES = SHOPS.map((s) => s.line);

/** Small sample drawings of each Pro section, so the locked list reads like
 *  the contents of a report rather than a set of buttons. Shapes are made up. */
const PREVIEWS: (() => JSX.Element)[] = [
  // price index: four lines around 100
  () => (
    <>
      <line x1="0" y1="32" x2="160" y2="32" className="pv-base" />
      {[
        "0,30 30,24 60,34 90,18 120,14 160,8",
        "0,34 30,40 60,28 90,42 120,46 160,40",
        "0,31 30,36 60,22 90,28 120,20 160,24",
        "0,36 30,28 60,44 90,50 120,42 160,56",
      ].map((pts, i) => (
        <polyline key={i} points={pts} fill="none" stroke={LINES[i]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      ))}
    </>
  ),
  // who is cheapest: one bar split by shop share
  () => (
    <>
      {[
        [0, 58],
        [60, 34],
        [96, 40],
        [138, 22],
      ].map(([x, w], i) => (
        <rect key={i} x={x} y="18" width={w} height="16" rx="3" fill={LINES[i]} />
      ))}
      {[0, 60, 96, 138].map((x, i) => (
        <rect key={i} x={x} y="40" width="16" height="4" rx="2" fill={LINES[i]} opacity=".45" />
      ))}
    </>
  ),
  // biggest moves: diverging bars
  () => (
    <>
      <line x1="80" y1="4" x2="80" y2="60" className="pv-base" />
      {[
        [-52, "var(--down)"],
        [-38, "var(--down)"],
        [-24, "var(--down)"],
        [30, "var(--up)"],
        [44, "var(--up)"],
      ].map(([w, c], i) => (
        <rect key={i} x={(w as number) < 0 ? 80 + (w as number) : 80} y={6 + i * 11} width={Math.abs(w as number)} height="7" rx="2" fill={c as string} />
      ))}
    </>
  ),
  // gaps: low-to-high ranges
  () => (
    <>
      {[
        [18, 92],
        [40, 140],
        [30, 70],
        [56, 120],
      ].map(([a, b], i) => (
        <g key={i}>
          <line x1={a} y1={10 + i * 14} x2={b} y2={10 + i * 14} className="pv-range" />
          <circle cx={a} cy={10 + i * 14} r="4" fill={LINES[(i + 1) % 4]} />
          <circle cx={b} cy={10 + i * 14} r="4" fill={LINES[i % 4]} />
        </g>
      ))}
    </>
  ),
  // brand x shop map
  () => (
    <>
      {Array.from({ length: 4 }, (_, r) =>
        Array.from({ length: 8 }, (_, c) => {
          const v = [0.15, 0.55, 0.3, 0.8, 0.45, 0.2, 0.65, 0.35][(c + r * 3) % 8];
          return <rect key={`${r}-${c}`} x={c * 20} y={r * 15 + 2} width="17" height="12" rx="2.5" fill="var(--accent)" opacity={v} />;
        }),
      )}
    </>
  ),
  // export: the four formats
  () => (
    <>
      {["XLSX", "PDF", "CSV", "JSON"].map((f, i) => (
        <g key={f}>
          <rect x={i * 40} y="14" width="34" height="40" rx="5" className="pv-file" />
          <text x={i * 40 + 17} y="38" textAnchor="middle" className="pv-fmt">
            {f}
          </text>
        </g>
      ))}
    </>
  ),
];

/** What a Free user sees in place of a Pro feature: the price, what Pro adds
 *  and how to get it while payments are not live yet. */
export default function ProGate({ titleId = "gate-h" }: { titleId?: string }) {
  const t = useT();
  const [asked, setAsked] = useState(false);
  return (
    <section aria-labelledby={titleId}>
      <div className="gate">
        <div className="gate-card rise">
          <span className="tag tag-pro" style={{ width: "fit-content" }}>
            {t.pro.gateKicker}
          </span>
          <h2 className="h2" id={titleId}>
            {t.pro.gateTitle}
          </h2>
          <p>{t.pro.pitch}</p>
          <div className="price">
            <b className="num">{eur(PRO_PRICE)}</b>
            <span>{t.pro.perMonth}</span>
          </div>
          <ul>
            {t.pro.benefits.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <div className="acts">
            <button className="btn btn-accent" type="button" onClick={() => setAsked(true)} aria-expanded={asked}>
              {t.pro.get}
            </button>
          </div>
          {asked && (
            <p className="note fade" role="status">
              {t.pro.manualNote}
            </p>
          )}
        </div>
        <div className="gate-side rise">
          <div className="gate-side-h">
            <b className="gate-side-k">{t.pro.sideKicker}</b>
            <small>{t.pro.preview}</small>
          </div>
          <ul className="locks">
            {t.pro.locks.map((l, i) => {
              const Preview = PREVIEWS[i % PREVIEWS.length];
              return (
                <li key={l} className="lock">
                  <svg viewBox="0 0 160 64" className="pv" aria-hidden="true">
                    <Preview />
                  </svg>
                  <div>
                    <b>{l}</b>
                    <small>{t.pro.lockNotes[i]}</small>
                  </div>
                  <Lock className="lk" aria-hidden="true" />
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}
