import { useCallback, useRef } from "react";

/** A bottle photo that follows the pointer over table rows marked with
 *  data-img (and optional data-field for the pastel behind it).
 *  Returns a callback ref: the rows often appear only after data loads,
 *  so listeners attach whenever the element mounts. */
export default function usePeek<T extends HTMLElement>() {
  const cleanup = useRef<(() => void) | null>(null);

  return useCallback((host: T | null) => {
    cleanup.current?.();
    cleanup.current = null;
    if (!host || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    let el = document.querySelector<HTMLDivElement>(".peek");
    if (!el) {
      el = document.createElement("div");
      el.className = "peek";
      el.setAttribute("aria-hidden", "true");
      document.body.appendChild(el);
    }
    const peek = el;
    const place = (e: PointerEvent) => {
      let x = e.clientX + 28;
      let y = e.clientY - 140;
      if (x + 240 > innerWidth) x = e.clientX - 258;
      y = Math.max(12, Math.min(innerHeight - 292, y));
      peek.style.transform = `translate(${x}px,${y}px)`;
    };
    const over = (e: PointerEvent) => {
      const r = (e.target as HTMLElement).closest<HTMLElement>("[data-img]");
      if (!r || !host.contains(r)) return;
      if (peek.dataset.src !== r.dataset.img) {
        peek.dataset.src = r.dataset.img!;
        peek.innerHTML = "";
        const img = document.createElement("img");
        img.src = r.dataset.img!;
        img.alt = "";
        peek.appendChild(img);
      }
      peek.style.setProperty("--field", r.dataset.field || "var(--card)");
      place(e);
      peek.classList.add("on");
    };
    const out = (e: PointerEvent) => {
      const to = e.relatedTarget as HTMLElement | null;
      if (!to || !to.closest || !to.closest("[data-img]")) peek.classList.remove("on");
    };
    const leave = () => peek.classList.remove("on");
    host.addEventListener("pointerover", over);
    host.addEventListener("pointermove", place);
    host.addEventListener("pointerout", out);
    host.addEventListener("pointerleave", leave);
    cleanup.current = () => {
      host.removeEventListener("pointerover", over);
      host.removeEventListener("pointermove", place);
      host.removeEventListener("pointerout", out);
      host.removeEventListener("pointerleave", leave);
      peek.classList.remove("on");
    };
  }, []);
}
