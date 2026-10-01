import { cn } from "@/lib/utils";

interface PromoCodePriceProps {
  price?: number | null;
  code?: string | null;
  className?: string;
}

/** The shop's price with a promo code, shown under the regular price. */
export function PromoCodePrice({ price, code, className }: PromoCodePriceProps) {
  if (!price || !code) return null;
  return (
    <span
      className={cn("font-mono text-[10px] tabular-nums font-medium text-primary whitespace-nowrap", className)}
      title={`Price with the promo code ${code.toUpperCase()}`}
    >
      {price.toFixed(2)} € with code <span className="font-semibold">{code.toUpperCase()}</span>
    </span>
  );
}
