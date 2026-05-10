import { useEffect, useState } from "react";

/**
 * Reveals `text` progressively at `msPerChar` ms per character once `trigger`
 * flips true. Honors `prefers-reduced-motion` (returns full text immediately).
 */
export function useTypewriter(
  text: string,
  msPerChar = 22,
  trigger = true
): { text: string; done: boolean } {
  const [shown, setShown] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!trigger) {
      setShown("");
      setDone(false);
      return;
    }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setShown(text);
      setDone(true);
      return;
    }
    let i = 0;
    setShown("");
    setDone(false);
    const id = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
        setDone(true);
      }
    }, msPerChar);
    return () => clearInterval(id);
  }, [text, msPerChar, trigger]);

  return { text: shown, done };
}
