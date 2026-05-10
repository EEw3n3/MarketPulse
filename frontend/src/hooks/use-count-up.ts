import { useEffect, useState } from "react";

/**
 * Animates a numeric value from 0 → target over `durationMs` once `trigger`
 * flips true. Suffix (e.g. "+", "mo") is preserved. Returns the formatted
 * string. Honors `prefers-reduced-motion`.
 */
export function useCountUp(target: string, durationMs = 1200, trigger = true): string {
  const [value, setValue] = useState("0");

  useEffect(() => {
    if (!trigger) return;

    const match = target.match(/^([\d,]+)(.*)$/);
    if (!match) {
      setValue(target);
      return;
    }
    const numStr = match[1].replace(/,/g, "");
    const targetNum = parseInt(numStr, 10);
    const suffix = match[2];
    if (Number.isNaN(targetNum)) {
      setValue(target);
      return;
    }

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setValue(targetNum.toLocaleString("en-US") + suffix);
      return;
    }

    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      const cur = Math.floor(targetNum * eased);
      setValue(cur.toLocaleString("en-US") + suffix);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs, trigger]);

  return value;
}
