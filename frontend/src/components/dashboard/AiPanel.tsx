import { X, Send, MessageSquare } from "lucide-react";
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
        {/* FAB button */}
        <button
          onClick={onOpen}
          className={`fixed bottom-20 right-4 z-50 w-14 h-14 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-lg shadow-primary/25 hover:scale-110 transition-all duration-300 ${
            open ? "opacity-0 pointer-events-none scale-90" : "opacity-100 scale-100"
          }`}
        >
          <MessageSquare size={22} />
        </button>

        {/* Fullscreen panel */}
        {open && (
          <div className="fixed inset-0 z-50 bg-surface flex flex-col animate-fade-in">
            {/* Header */}
            <div className="h-14 flex items-center gap-3 px-4 border-b border-border shrink-0">
              <span className="relative w-2.5 h-2.5">
                <span className="absolute inset-0 rounded-full bg-primary animate-pulse" />
                <span className="absolute inset-0 rounded-full bg-primary" />
              </span>
              <span className="text-[15px] font-bold text-foreground font-display tracking-tight">MarketPulse AI</span>
              <button
                onClick={onClose}
                className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="flex justify-end">
                <div className="max-w-[85%] bg-primary text-primary-foreground text-[13px] px-3 py-2 rounded-tl-2xl rounded-bl-2xl rounded-tr-sm border border-primary/20" style={{ boxShadow: "0 4px 16px rgba(124,58,237,0.3), inset 0 1px 0 rgba(255,255,255,0.15)" }}>
                  Show me the cheapest Dior Sauvage EDP 100ml across all stores
                </div>
              </div>
              <div className="flex justify-start">
                <div className="max-w-[85%] bg-[rgba(255,255,255,0.03)] backdrop-blur-[12px] border border-border text-foreground text-[13px] px-3 py-2 rounded-tr-2xl rounded-br-2xl rounded-tl-sm shadow-sm">
                  I found Dior Sauvage EDP 100ml listed on 4 stores. The best price is currently <span className="text-secondary font-semibold font-display tabular-nums tracking-tight">€78.90</span> at Notino, which is 12% below the average.
                </div>
              </div>
              <div className="flex justify-start">
                <div className="flex items-center gap-1 bg-[rgba(255,255,255,0.03)] backdrop-blur-[12px] border border-border px-3 py-2.5 rounded-tr-2xl rounded-br-2xl rounded-tl-sm shadow-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0s" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0.15s" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0.3s" }} />
                </div>
              </div>
            </div>

            {/* Chips */}
            <div className="px-4 pb-2 flex flex-wrap gap-1.5">
              {suggestedChips.map((chip) => (
                <button
                  key={chip}
                  className="px-2.5 py-1 rounded-full bg-[rgba(255,255,255,0.02)] backdrop-blur-md text-[11px] text-muted-foreground hover:text-foreground transition-all duration-200 border border-border hover:border-primary/50 hover:bg-surface-2"
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Input */}
            <div className="p-3 pb-safe border-t border-border bg-surface/50 backdrop-blur-md">
              <div className="flex items-end gap-2 bg-surface-2/50 border border-border rounded-xl p-1.5 focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/50 transition-all duration-200 shadow-inner">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask MarketPulse AI..."
                  rows={1}
                  className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none max-h-24 px-2 py-1.5"
                />
                <button className="w-8 h-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shrink-0 hover:brightness-110 transition shadow-[0_2px_8px_rgba(124,58,237,0.4)]">
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  // Desktop/tablet: side panel
  return (
    <>
      {/* Floating open button when panel is closed */}
      <button
        onClick={onOpen}
        className={`fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-lg shadow-primary/25 hover:scale-110 transition-all duration-300 ${
          open ? "opacity-0 pointer-events-none scale-90" : "opacity-100 scale-100"
        }`}
      >
        <MessageSquare size={20} />
      </button>

      <aside
        data-tutorial="ai-panel"
        className={`h-full flex-col bg-surface border-l border-border shrink-0 transition-all duration-300 ease-in-out overflow-hidden hidden md:flex ${
          open ? "w-[360px] opacity-100" : "w-0 opacity-0 border-l-0"
        }`}
      >
        {/* Header */}
        <div className="h-14 flex items-center gap-3 px-4 border-b border-border shrink-0 min-w-[360px]">
          <span className="relative w-2.5 h-2.5">
            <span className="absolute inset-0 rounded-full bg-primary animate-pulse" />
            <span className="absolute inset-0 rounded-full bg-primary" />
          </span>
          <span className="text-[15px] font-bold text-foreground font-display tracking-tight">MarketPulse AI</span>
          <button
            onClick={onClose}
            className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-w-[360px]">
          <div className="flex justify-end">
            <div className="max-w-[80%] bg-primary text-primary-foreground text-[13px] px-3 py-2 rounded-tl-2xl rounded-bl-2xl rounded-tr-sm border border-primary/20" style={{ boxShadow: "0 4px 16px rgba(124,58,237,0.3), inset 0 1px 0 rgba(255,255,255,0.15)" }}>
              Show me the cheapest Dior Sauvage EDP 100ml across all stores
            </div>
          </div>
          <div className="flex justify-start">
            <div className="max-w-[80%] bg-[rgba(255,255,255,0.03)] backdrop-blur-[12px] border border-border text-foreground text-[13px] px-3 py-2 rounded-tr-2xl rounded-br-2xl rounded-tl-sm shadow-sm">
              I found Dior Sauvage EDP 100ml listed on 4 stores. The best price is currently <span className="text-secondary font-semibold font-display tabular-nums tracking-tight">€78.90</span> at Notino, which is 12% below the average.
            </div>
          </div>
          {/* AI typing indicator */}
          <div className="flex justify-start">
            <div className="flex items-center gap-1 bg-[rgba(255,255,255,0.03)] backdrop-blur-[12px] border border-border px-3 py-2.5 rounded-tr-2xl rounded-br-2xl rounded-tl-sm shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0s" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0.15s" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-typing-dot" style={{ animationDelay: "0.3s" }} />
            </div>
          </div>
        </div>

        {/* Suggested chips */}
        <div className="px-4 pb-2 flex flex-wrap gap-1.5 min-w-[360px]">
          {suggestedChips.map((chip) => (
            <button
              key={chip}
              className="px-2.5 py-1 rounded-full bg-[rgba(255,255,255,0.02)] backdrop-blur-md text-[11px] text-muted-foreground hover:text-foreground transition-all duration-200 border border-border hover:border-primary/50 hover:bg-surface-2"
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Input */}
        <div className="p-3 min-w-[360px] border-t border-border bg-surface/50 backdrop-blur-md">
          <div className="flex items-end gap-2 bg-surface-2/50 border border-border rounded-xl p-1.5 focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/50 transition-all duration-200 shadow-inner">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask MarketPulse AI..."
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none max-h-24 px-2 py-1.5"
            />
            <button className="w-8 h-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shrink-0 hover:brightness-110 transition shadow-[0_2px_8px_rgba(124,58,237,0.4)]">
              <Send size={14} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
