import { useState, useCallback } from "react";

const STORAGE_KEY = "marketpulse-ai-panel-open";

function getInitialState(isMobile: boolean): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return stored === "true";
  } catch {}
  return !isMobile;
}

export function useAiPanel(isMobile: boolean) {
  const [open, setOpenState] = useState(() => getInitialState(isMobile));

  const setOpen = useCallback((value: boolean) => {
    setOpenState(value);
    try { localStorage.setItem(STORAGE_KEY, String(value)); } catch {}
  }, []);

  return { aiPanelOpen: open, setAiPanelOpen: setOpen };
}
