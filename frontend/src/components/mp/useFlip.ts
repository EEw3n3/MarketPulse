import { useLayoutEffect, useRef } from "react";

/** Slides children marked with data-key from their old place to the new one
 *  when the list changes (search, filters, sort). New children keep their
 *  own entrance animation. Positions are kept relative to the container, so
 *  scrolling between two renders does not count as movement. */
export default function useFlip<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T>(null);
  const prev = useRef(new Map<string, { x: number; y: number }>());

  useLayoutEffect(() => {
    const host = ref.current;
    const next = new Map<string, { x: number; y: number }>();
    if (host) {
      const base = host.getBoundingClientRect();
      const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
      host.querySelectorAll<HTMLElement>(":scope > [data-key]").forEach((el) => {
        const r = el.getBoundingClientRect();
        const at = { x: r.left - base.left, y: r.top - base.top };
        const key = el.dataset.key!;
        next.set(key, at);
        const was = prev.current.get(key);
        if (still || !was || typeof el.animate !== "function") return;
        const dx = was.x - at.x;
        const dy = was.y - at.y;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
        el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], {
          duration: 560,
          easing: "cubic-bezier(.16, 1, .3, 1)",
        });
      });
    }
    prev.current = next;
  }, [dep]);

  return ref;
}
