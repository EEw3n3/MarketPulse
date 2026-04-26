import { useEffect, useState } from "react";

/**
 * Tracks which of the given anchor IDs is currently in view. Returns the active
 * id (the topmost section whose top edge has crossed the offset line).
 *
 * - `containerSelector` — the scroll container; pass null for window
 * - `offset` — how far below the top of the viewport the "active line" sits
 */
export function useScrollSpy(
  ids: string[],
  containerSelector: string | null = null,
  offset = 100
): string {
  const [active, setActive] = useState<string>(ids[0] ?? "");

  useEffect(() => {
    const container = containerSelector
      ? (document.querySelector(containerSelector) as HTMLElement | null)
      : null;
    const scroller: HTMLElement | Window = container ?? window;

    const compute = () => {
      const containerTop = container ? container.getBoundingClientRect().top : 0;
      let current = ids[0] ?? "";
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        const top = el.getBoundingClientRect().top - containerTop;
        if (top - offset <= 0) {
          current = id;
        } else {
          break;
        }
      }
      setActive((prev) => (prev === current ? prev : current));
    };

    compute();
    scroller.addEventListener("scroll", compute, { passive: true });
    window.addEventListener("resize", compute);
    return () => {
      scroller.removeEventListener("scroll", compute);
      window.removeEventListener("resize", compute);
    };
  }, [ids.join("|"), containerSelector, offset]);

  return active;
}
