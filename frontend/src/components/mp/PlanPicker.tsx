import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api, type BillingTerm } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";
import { eur } from "@/lib/format";
import { PRO_PRICES, PRO_TERMS, termDeal } from "@/lib/plan";
import { openCheckout } from "@/lib/paddle";

type State = "idle" | "opening" | "waiting" | "slow" | "soon";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Pro plans (month, 6 months, year) and the button that opens Paddle's
 *  checkout. Sits on the dark Pro cards (the analytics gate, Profile → Plan).
 *  Without a live checkout for this user the button says payments open soon. */
export default function PlanPicker() {
  const t = useT();
  const qc = useQueryClient();
  const { user, refreshUser } = useAuth();
  const [term, setTerm] = useState<BillingTerm>("year");
  const [state, setState] = useState<State>("idle");
  const { data: cfg } = useQuery({
    queryKey: ["billing", "config", user?.id],
    queryFn: api.billing.config,
    enabled: !!user,
    staleTime: 5 * 60_000,
  });

  /** The webhook turns Pro on a few seconds after the payment: ask the server until it has. */
  async function waitForPro() {
    setState("waiting");
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const sub = await api.billing.me();
        if (sub && sub.status !== "canceled") {
          await refreshUser();
          qc.invalidateQueries({ queryKey: ["billing"] });
          setState("idle");
          toast.success(t.pro.done);
          return;
        }
      } catch {
        /* try again */
      }
    }
    setState("slow");
  }

  async function buy() {
    const plan = cfg?.plans.find((p) => p.term === term);
    if (!user || !cfg?.checkout || !plan?.price_id) {
      setState("soon");
      return;
    }
    setState("opening");
    try {
      await openCheckout({
        config: cfg,
        priceId: plan.price_id,
        email: user.email,
        userId: user.id,
        onEvent: (e) => {
          if (e.name === "checkout.completed") void waitForPro();
          else if (e.name === "checkout.closed") setState((s) => (s === "opening" ? "idle" : s));
        },
      });
      setState((s) => (s === "opening" ? "idle" : s));
    } catch {
      setState("idle");
      toast.error(t.pro.loadFail);
    }
  }

  return (
    <div className="plans-pick">
      <div className="terms" role="radiogroup" aria-label={t.pro.pickTerm}>
        {PRO_TERMS.map((k) => {
          const { amount } = PRO_PRICES[k];
          const deal = termDeal(k);
          return (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={term === k}
              className="term"
              onClick={() => setTerm(k)}
            >
              <span className="tn">
                {t.pro.terms[k]}
                {deal.save > 0 && <span className="save">{t.pro.save(deal.save)}</span>}
              </span>
              <b className="num">{eur(amount)}</b>
              <small>{k === "month" ? t.pro.billed.month : t.pro.perMonthEq(eur(deal.perMonth))}</small>
            </button>
          );
        })}
      </div>
      {cfg && !cfg.checkout ? (
        // No checkout for this account yet (test mode, or keys not set): no button, just say so.
        <p className="note" role="status">
          {t.pro.manualNote}
        </p>
      ) : (
        <div className="acts">
          <button className="btn btn-accent" type="button" onClick={buy} disabled={!cfg || state === "opening" || state === "waiting"}>
            {state === "opening" ? t.pro.opening : state === "waiting" ? t.pro.waiting : t.pro.get}
          </button>
        </div>
      )}
      {state === "soon" ? (
        <p className="note fade" role="status">
          {t.pro.manualNote}
        </p>
      ) : state === "slow" ? (
        <p className="note fade" role="status">
          {t.pro.slow}
        </p>
      ) : (
        <p className="fine">
          {cap(t.pro.billed[term])} · {t.pro.paddleNote}{" "}
          <Link to="/refunds">{t.pro.refundLink}</Link>
        </p>
      )}
      {cfg?.checkout && cfg.environment === "sandbox" && <p className="fine sandbox">{t.pro.sandbox}</p>}
    </div>
  );
}
