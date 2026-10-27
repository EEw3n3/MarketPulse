import type { UserRead } from "@/lib/api";

// Placeholder until card payments arrive; an admin switches Pro on by hand.
export const PRO_PRICE = 3.99;

export function hasPro(user: Pick<UserRead, "is_admin" | "plan"> | null | undefined): boolean {
  return !!user && (user.is_admin || user.plan === "pro");
}
