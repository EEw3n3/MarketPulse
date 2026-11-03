import type { BillingTerm, UserRead } from "@/lib/api";
import { hoursUntil } from "@/lib/format";

/** Pro prices in EUR (the same as app/services/billing.py PLANS); Paddle's checkout shows the final price. */
export const PRO_PRICES: Record<BillingTerm, { amount: number; months: number }> = {
  month: { amount: 3.99, months: 1 },
  half: { amount: 19.99, months: 6 },
  year: { amount: 34.99, months: 12 },
};
export const PRO_TERMS: BillingTerm[] = ["month", "half", "year"];
export const PRO_PRICE = PRO_PRICES.month.amount;

/** Per-month price of a term and how much it saves against paying monthly, in whole percent. */
export function termDeal(term: BillingTerm): { perMonth: number; save: number } {
  const { amount, months } = PRO_PRICES[term];
  const perMonth = amount / months;
  return { perMonth, save: Math.round((1 - perMonth / PRO_PRICE) * 100) };
}

/** The banner "Pro until 30.11" shows this many days before the end (the site sends no e-mails). */
export const PRO_WARN_DAYS = 3;

type PlanUser = Pick<UserRead, "is_admin" | "plan" | "is_pro" | "pro_until">;

/** Pro screens open. The server decides (is_pro: admin, or a term that has not ended). */
export function hasPro(user: PlanUser | null | undefined): boolean {
  if (!user) return false;
  if (typeof user.is_pro === "boolean") return user.is_pro;
  return user.is_admin || user.plan === "pro";
}

/** The end of the user's own Pro term when it is less than PRO_WARN_DAYS away. */
export function proEndingSoon(user: PlanUser | null | undefined): string | null {
  if (!user || !hasPro(user) || user.plan !== "pro" || !user.pro_until) return null;
  const h = hoursUntil(user.pro_until);
  return h != null && h > 0 && h <= PRO_WARN_DAYS * 24 ? user.pro_until : null;
}
