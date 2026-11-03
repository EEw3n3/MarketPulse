import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import { dayLong } from "@/lib/format";
import { CONTACT } from "@/i18n/sections/legal";
import LangSwitch from "@/components/mp/LangSwitch";

/** /privacy, /terms and /refunds: public, also for people who are not signed in. */
export default function Legal({ page }: { page: "privacy" | "terms" | "refunds" }) {
  const t = useT();
  const { user } = useAuth();
  const L = t.legal;
  const sections = page === "privacy" ? L.privacy : page === "refunds" ? L.refunds : L.terms;
  return (
    <div className="pg-legal wrap">
      <div className="nf-top">
        <Link className="logo" to={user ? "/today" : "/"}>
          MarketPulse
        </Link>
        <LangSwitch />
      </div>
      <main className="doc">
        <h1>{page === "privacy" ? L.privacyH : page === "refunds" ? L.refundsH : L.termsH}</h1>
        <p className="muted">
          {L.updated}: {dayLong(L.date)}
        </p>
        {sections.map((s) => (
          <section key={s.h}>
            <h2>{s.h}</h2>
            {s.p.map((x) => (
              <p key={x}>{x}</p>
            ))}
          </section>
        ))}
        <p className="muted foot">
          {L.contact}: <a href={`mailto:${CONTACT}`}>{CONTACT}</a> · <Link to={page === "privacy" ? "/terms" : page === "refunds" ? "/terms" : "/privacy"}>{L.other[page]}</Link>
          {page !== "refunds" && (
            <>
              {" "}
              · <Link to="/refunds">{L.refundsH}</Link>
            </>
          )}
        </p>
      </main>
    </div>
  );
}
