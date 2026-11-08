import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// The floating AI chat lives once in the app. Pages tell it what the user is
// looking at (sent to the assistant with each question) and can open it with
// a question already asked.

interface ChatValue {
  open: boolean;
  setOpen: (v: boolean) => void;
  pageContext: string;
  setPageContext: (s: string) => void;
  /** The product page the chat is open on: the assistant answers "is this a good price?" for it. */
  productId: number | null;
  setProductId: (id: number | null) => void;
  pending: string | null;
  ask: (question: string) => void;
  takePending: () => string | null;
}

const ChatContext = createContext<ChatValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [pageContext, setPageContext] = useState("");
  const [productId, setProductId] = useState<number | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  const ask = useCallback((q: string) => {
    setPending(q);
    setOpen(true);
  }, []);

  const takePending = useCallback(() => {
    const q = pending;
    setPending(null);
    return q;
  }, [pending]);

  const value = useMemo(
    () => ({ open, setOpen, pageContext, setPageContext, productId, setProductId, pending, ask, takePending }),
    [open, pageContext, productId, pending, ask, takePending],
  );
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}

/** Tell the assistant what this page shows; cleared when the page unmounts. */
export function usePageContext(text: string) {
  const { setPageContext } = useChat();
  useEffect(() => {
    setPageContext(text);
  }, [text, setPageContext]);
  useEffect(() => () => setPageContext(""), [setPageContext]);
}

/** The product this page shows; cleared when the page unmounts. */
export function usePageProduct(id: number | null | undefined) {
  const { setProductId } = useChat();
  useEffect(() => {
    setProductId(id ?? null);
  }, [id, setProductId]);
  useEffect(() => () => setProductId(null), [setProductId]);
}
