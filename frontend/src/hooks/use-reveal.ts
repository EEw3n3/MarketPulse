import { useEffect, useRef, useState } from "react";

/**
 * Returns a ref + boolean. The boolean flips to true the first time the element
 * intersects the viewport. Used to trigger CSS reveal animations on scroll.
 *
 * Once revealed, stays revealed (no flicker on re-entry).
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(
  rootMargin = "0px 0px -10% 0px"
): { ref: React.RefObject<T>; revealed: boolean } {
  const ref = useRef<T>(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Honor user motion preferences
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setRevealed(true);
      return;
    }

    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setRevealed(true);
            obs.disconnect();
            break;
          }
        }
      },
      { rootMargin, threshold: 0.05 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [rootMargin]);

  return { ref, revealed };
}
