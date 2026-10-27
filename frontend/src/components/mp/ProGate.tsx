import { useState } from "react";
import { BarChart3, Download, LineChart as LineIcon, Map, Scale, TrendingDown } from "lucide-react";
import { useT } from "@/i18n";
import { eur } from "@/lib/format";
import { PRO_PRICE } from "@/lib/plan";

const LOCK_FIELDS = ["var(--f-notino)", "var(--f-makeup)", "var(--f-220)", "var(--f-douglas)", "var(--f-1a)", "var(--surface)"];
const LOCK_ICONS = [LineIcon, Scale, TrendingDown, BarChart3, Map, Download];

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
        <div className="gate-side">
          {t.pro.locks.map((l, i) => {
            const Icon = LOCK_ICONS[i % LOCK_ICONS.length];
            return (
              <div key={l} className="lock rise" style={{ ["--field" as string]: LOCK_FIELDS[i % LOCK_FIELDS.length], ["--i" as string]: i + 1 } as React.CSSProperties}>
                <Icon aria-hidden="true" />
                <b>{l}</b>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
