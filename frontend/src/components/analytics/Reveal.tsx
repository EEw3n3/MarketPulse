import { ReactNode } from "react";
import { useReveal } from "@/hooks/use-reveal";
import { cn } from "@/lib/utils";

interface RevealProps {
  children: ReactNode;
  delayMs?: number;
  className?: string;
  as?: "div" | "section";
  id?: string;
}

/**
 * Wraps a block; when it scrolls into view, fades + slides up. Idempotent —
 * once revealed, stays revealed, so re-scrolling doesn't re-trigger.
 */
export default function Reveal({
  children,
  delayMs = 0,
  className,
  as = "div",
  id,
}: RevealProps) {
  const { ref, revealed } = useReveal<HTMLDivElement>();
  const Comp = as as "div";
  return (
    <Comp
      ref={ref}
      id={id}
      className={cn(
        "transition-[opacity,transform] duration-700 ease-out will-change-[opacity,transform]",
        revealed ? "opacity-100 translate-y-0" : "opacity-0 translate-y-7",
        className
      )}
      style={{ transitionDelay: revealed ? `${delayMs}ms` : "0ms" }}
    >
      {children}
    </Comp>
  );
}
