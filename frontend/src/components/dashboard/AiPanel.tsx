import { X, Send, Sparkles, MessageSquare, Trash2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useIsMobile } from "@/hooks/use-mobile";
import { api, type ChatMessage } from "@/lib/api";

const CHAT_STORAGE_KEY = "marketpulse_chat_history";
const MAX_STORED_MESSAGES = 40;

function loadMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(msgs: ChatMessage[]) {
  try {
    // Keep only the last N messages to avoid localStorage limits
    const toStore = msgs.slice(-MAX_STORED_MESSAGES);
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toStore));
  } catch {
    // Storage quota exceeded — ignore silently
  }
}

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

function PanelHeader({
  onClose,
  onClear,
}: {
  onClose?: () => void;
  onClear?: () => void;
}) {
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
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={onClear}
          title="Clear chat history"
          className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
        >
          <Trash2 size={13} />
        </button>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

function ConversationArea({
  messages,
  isLoading,
  scrollRef,
}: {
  messages: ChatMessage[];
  isLoading: boolean;
  scrollRef: React.RefObject<HTMLDivElement>;
}) {
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 overflow-y-auto p-4 flex items-center justify-center">
        <p className="font-mono text-[11px] text-muted-foreground text-center uppercase tracking-[0.12em]">
          Ask me anything about prices,
          <br />
          trends, or your watchlist
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((msg, i) =>
        msg.role === "user" ? (
          <div key={i} className="flex justify-end">
            <div className="max-w-[82%] bg-foreground text-background text-[12.5px] px-3 py-2 rounded-md leading-relaxed whitespace-pre-wrap">
              {msg.content}
            </div>
          </div>
        ) : (
          <div key={i} className="flex flex-col gap-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Assistant
            </span>
            <div className="border-l-2 border-primary pl-3 text-[13px] text-foreground leading-relaxed whitespace-pre-wrap">
              {msg.content}
            </div>
          </div>
        )
      )}

      {isLoading && (
        <div className="flex items-center gap-1.5 px-1">
          <span
            className="w-1 h-1 rounded-full bg-muted-foreground animate-typing-dot"
            style={{ animationDelay: "0s" }}
          />
          <span
            className="w-1 h-1 rounded-full bg-muted-foreground animate-typing-dot"
            style={{ animationDelay: "0.15s" }}
          />
          <span
            className="w-1 h-1 rounded-full bg-muted-foreground animate-typing-dot"
            style={{ animationDelay: "0.3s" }}
          />
        </div>
      )}

      {/* Invisible anchor for auto-scroll */}
      <div ref={scrollRef} />
    </div>
  );
}

function SuggestedChips({
  onChipClick,
  show,
}: {
  onChipClick: (text: string) => void;
  show: boolean;
}) {
  if (!show) return null;
  return (
    <div className="px-4 pb-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-2">
        Try
      </p>
      <div className="flex flex-wrap gap-1.5">
        {suggestedChips.map((chip) => (
          <button
            key={chip}
            onClick={() => onChipClick(chip)}
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
  onSend,
  isLoading,
  textareaRef,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  isLoading: boolean;
  textareaRef: React.RefObject<HTMLTextAreaElement>;
}) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="p-3 border-t border-border">
      <div className="flex items-end gap-2 bg-surface border border-border rounded-md p-1.5 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-colors">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about prices, trends, availability…"
          rows={1}
          disabled={isLoading}
          className="flex-1 resize-none bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground outline-none max-h-24 px-2 py-1.5 disabled:opacity-50"
        />
        <button
          onClick={onSend}
          disabled={isLoading || !input.trim()}
          className="w-7 h-7 rounded bg-foreground text-background flex items-center justify-center shrink-0 hover:bg-foreground/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
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
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    saveMessages(messages);
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        textareaRef.current.scrollHeight + "px";
    }
  }, [input]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleClear = () => {
    setMessages([]);
    localStorage.removeItem(CHAT_STORAGE_KEY);
  };

  const handleSend = async (chipText?: string) => {
    const text = chipText ?? input;
    if (!text.trim() || isLoading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const historySnapshot = messages.slice(-6);

    setMessages((prev) => [...prev, userMsg]);
    if (!chipText) setInput("");
    setIsLoading(true);

    try {
      const res = await api.sendChat(text, historySnapshot);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Something went wrong. Please try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const showChips = messages.length === 0 && !isLoading;

  const panelContent = (
    <>
      <PanelHeader onClose={onClose} onClear={handleClear} />
      <ConversationArea
        messages={messages}
        isLoading={isLoading}
        scrollRef={scrollRef}
      />
      <SuggestedChips onChipClick={handleSend} show={showChips} />
      <InputArea
        input={input}
        setInput={setInput}
        onSend={() => handleSend()}
        isLoading={isLoading}
        textareaRef={textareaRef}
      />
    </>
  );

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
            {panelContent}
          </div>
        )}
      </>
    );
  }

  return (
    <>
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
          {panelContent}
        </div>
      </aside>
    </>
  );
}
