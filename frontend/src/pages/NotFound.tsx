import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import LangSwitch from "@/components/mp/LangSwitch";

export default function NotFound() {
  const t = useT();
  const { user } = useAuth();
  return (
    <div className="pg-nf wrap">
      <div className="nf-top">
        <Link className="logo" to={user ? "/today" : "/"}>
          MarketPulse
        </Link>
        <LangSwitch />
      </div>
      <main className="empty">
        <p className="nf-code serif num" aria-hidden="true">
          404
        </p>
        <h1>{t.common.notFoundTitle}</h1>
        <p>{t.common.notFoundText}</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
          <Link className="btn btn-ink" to={user ? "/today" : "/"}>
            {user ? t.common.goHome : t.common.goStart}
          </Link>
          {user && (
            <Link className="btn btn-soft" to="/catalog">
              {t.shell.nav.catalog}
            </Link>
          )}
        </div>
      </main>
    </div>
  );
}
