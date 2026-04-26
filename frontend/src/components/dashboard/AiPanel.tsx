import { X, Send, Sparkles, MessageSquare } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useIsMobile } from "@/hooks/use-mobile";

const suggestedChips = [
  "What prices dropped this week?",
  "Best price for Dior Sauvage?",
  "Compare Hugo Boss across all sites",
];

interface AiPanelProps {
  open?: boolean;
  onClose?: () => void;
  onOpen?: () => void;
}

function PanelHeader({ onClose }: { onClose?: () => void }) {
  return (
    <div className="h-14 flex items-center gap-2.5 px-4 border-b border-border shrink-0">
      <div className="w-7 h-7 rounded-md bg-surface-2 border border-border flex items-center justify-center">
        <Sparkles size={13} className="text-primary" strokeWidth={2} />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="text-[13px] font-medium text-foreground font-['Inter']">
          MarketPulse AI
        </span>
        <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-[0.1em]">
          Grounded on your feed
        </span>
      </div>
      <button
        onClick={onClose}
        className="ml-auto w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}

function ConversationMock() {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* User */}
      <div className="flex justify-end">
        <div className="max-w-[82%] bg-foreground text-background text-[12.5px] px-3 py-2 rounded-md leading-relaxed">
          Show me the cheapest Dior Sauvage EDP 100ml across all stores.
        </div>
      </div>

      {/* Assistant */}
      <div className="flex flex-col gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          Assistant · 0.9s
        </span>
        <div className="border-l-2 border-primary pl-3 text-[13px] text-foreground leading-relaxed">
          Found <span className="font-mono tabular-nums">4</span> stores carrying it. Lowest is Notino
          at{" "}
          <span className="font-mono font-semibold tabular-nums text-foreground">78.90 €</span>,
          which is <span className="text-[hsl(var(--success))] font-medium">−12%</span> below the
          4-store average (<span className="font-mono tabular-nums">89.50 €</span>).
        </div>

        {/* Inline data card */}
        <div className="border border-border rounded-md divide-y divide-border bg-surface/60 overflow-hidden text-[12px]">
          {[
            { store: "Notino.lv", price: 78.9, best: true },
            { store: "Douglas.lv", price: 89.0, best: false },
            { store: "Makeup.lv", price: 92.5, best: false },
            { store: "1a.lv", price: 97.6, best: false },
          ].map((r) => (
            <div
              key={r.store}
              className="flex items-center justify-between px-3 py-2"
            >
              <span className={r.best ? "text-foreground font-medium" : "text-muted-foreground"}>
                {r.store}
              </span>
              <span
                className={`font-mono tabular-nums ${
                  r.best ? "text-[hsl(var(--success))] font-semibold" : "text-foreground"
                }`}
              >
                {r.price.toFixed(2)} €
              </span>
            </div>
          ))}
        </div>

        <span className="font-mono text-[10px] text-muted-foreground">
          Source · 4 product rows · updated 11:20
        </span>
      </div>

      {/* Typing indicator */}
      <div className="flex items-center gap-1.5 px-1">
        <span className="w-1 h-1 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0s" }} />
        <span className="w-1 h-1 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0.15s" }} />
        <span className="w-1 h-1 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0.3s" }} />
      </div>
    </div>
  );
}

function SuggestedChips() {
  return (
    <div className="px-4 pb-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2">
        Try
      </p>
      <div className="flex flex-wrap gap-1.5">
        {suggestedChips.map((chip) => (
          <button
            key={chip}
            className="px-2.5 py-1 rounded-md bg-surface border border-border text-[11.5px] text-muted-foreground hover:text-foreground hover:border-muted-foreground transition-colors"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}

function InputArea({
  input,
  setInput,
  textareaRef,
}: {
  input: string;
  setInput: (v: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement>;
}) {
  return (
    <div className="p-3 border-t border-border">
      <div className="flex items-end gap-2 bg-surface border border-border rounded-md p-1.5 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-colors">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about prices, trends, availability…"
          rows={1}
          className="flex-1 resize-none bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground outline-none max-h-24 px-2 py-1.5"
        />
        <button className="w-7 h-7 rounded bg-foreground text-background flex items-center justify-center shrink-0 hover:bg-foreground/90 transition-colors disabled:opacity-50">
          <Send size={12} strokeWidth={2} />
        </button>
      </div>
      <p className="font-mono text-[10px] text-muted-foreground mt-2 px-1">
        Enter to send · Shift+Enter for newline · Gemini-grounded
      </p>
    </div>
  );
}

export default function AiPanel({ open = true, onClose, onOpen }: AiPanelProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [input]);

  // Mobile: fullscreen overlay
  if (isMobile) {
    return (
      <>
        <button
          onClick={onOpen}
          className={`fixed bottom-20 right-4 z-50 w-12 h-12 rounded-full bg-foreground text-background flex items-center justify-center shadow-lg hover:bg-foreground/90 transition-all duration-200 ${
            open ? "opacity-0 pointer-events-none scale-90" : "opacity-100 scale-100"
          }`}
        >
          <MessageSquare size={18} />
        </button>

        {open && (
          <div className="fixed inset-0 z-50 bg-background flex flex-col animate-fade-in">
            <PanelHeader onClose={onClose} />
            <ConversationMock />
            <SuggestedChips />
            <InputArea input={input} setInput={setInput} textareaRef={textareaRef} />
          </div>
        )}
      </>
    );
  }

  return (
    <>
      {/* Floating open button */}
      <button
        onClick={onOpen}
        className={`fixed bottom-6 right-6 z-50 w-11 h-11 rounded-full bg-foreground text-background flex items-center justify-center shadow-[0_8px_24px_rgba(0,0,0,0.4)] hover:bg-foreground/90 transition-all duration-200 ${
          open ? "opacity-0 pointer-events-none scale-90" : "opacity-100 scale-100"
        }`}
      >
        <MessageSquare size={16} />
      </button>

      <aside
        data-tutorial="ai-panel"
        className={`h-full flex-col bg-surface/40 backdrop-blur-[20px] border-l border-border shrink-0 transition-all duration-300 ease-in-out overflow-hidden hidden md:flex ${
          open ? "w-[360px] opacity-100" : "w-0 opacity-0 border-l-0"
        }`}
      >
        <div className="min-w-[360px] h-full flex flex-col">
          <PanelHeader onClose={onClose} />
          <ConversationMock />
          <SuggestedChips />
          <InputArea input={input} setInput={setInput} textareaRef={textareaRef} />
        </div>
      </aside>
    </>
  );
}
